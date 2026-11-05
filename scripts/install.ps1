param([switch]$SemAtalho)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$MinMinor = 11
$MaxMinor = 15

function Test-Python($Exe, $PrefixArgs) {
    # Retorna a versão quando o Python serve; senão escreve o motivo e retorna nulo.
    $probe = "import struct,sys;print(sys.version_info[0],sys.version_info[1],struct.calcsize('P')*8)"
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Exe @PrefixArgs -c $probe 2>$null
        $code = $LASTEXITCODE
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $saved
    }
    if ($code -ne 0 -or -not $out) { return $null }
    $parts = ([string]$out).Trim() -split '\s+'
    $major, $minor, $bits = [int]$parts[0], [int]$parts[1], [int]$parts[2]
    if ($major -ne 3 -or $minor -lt $MinMinor -or $minor -gt $MaxMinor) {
        Write-Host "  Python $major.$minor ignorado (o Neku usa 3.$MinMinor a 3.$MaxMinor)."
        return $null
    }
    if ($bits -ne 64) {
        Write-Host "  Python $major.$minor de $bits bits ignorado (o Neku precisa de 64 bits)."
        return $null
    }
    return "$major.$minor"
}

function Get-NekuProcess {
    $scripts = Join-Path $Root ".venv\Scripts"
    $launchers = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($scripts, [StringComparison]::OrdinalIgnoreCase) })
    $children = @(foreach ($p in $launchers) {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.ProcessId)"
    })
    return @($launchers) + @($children)
}

Write-Host "Procurando Python 3.$MinMinor a 3.$MaxMinor de 64 bits..."

$found = $null
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    foreach ($minor in $MinMinor..$MaxMinor) {
        $version = Test-Python "py" @("-3.$minor")
        if ($version) { $found = @{ Exe = "py"; Args = @("-3.$minor"); Version = $version }; break }
    }
}
if (-not $found) {
    foreach ($name in "python", "python3") {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $version = Test-Python $cmd.Source @()
        if ($version) { $found = @{ Exe = $cmd.Source; Args = @(); Version = $version }; break }
    }
}

if (-not $found) {
    Write-Host ""
    Write-Host "Não encontrei um Python compatível." -ForegroundColor Red
    Write-Host "Instale o Python 3.12 (64 bits) em https://www.python.org/downloads/windows/"
    Write-Host "Durante a instalação, marque 'Add python.exe to PATH'."
    Write-Host "Depois feche esta janela e execute o instalador novamente."
    exit 1
}
Write-Host "Usando Python $($found.Version)."

$running = @(Get-NekuProcess)
if ($running.Count -gt 0) {
    Write-Host ""
    Write-Host "O Neku está aberto e precisa ser fechado antes de instalar." -ForegroundColor Yellow
    $answer = Read-Host "Encerrar o Neku agora? (s/N)"
    if ($answer -notmatch '^[sS]') {
        Write-Host "Instalação cancelada. Nada foi alterado."
        exit 1
    }
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Criando ambiente virtual limpo..."
& $found.Exe @($found.Args) -m venv --clear .venv
if ($LASTEXITCODE -ne 0) {
    throw "Não foi possível criar o ambiente virtual. Verifique a instalação do Python."
}

Write-Host "Instalando dependências do Neku (requer internet só nesta etapa)..."
& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Falha ao instalar dependências." -ForegroundColor Red
    Write-Host "Verifique a internet. Se o erro citar caminho longo, mova o Neku para uma pasta mais curta."
    exit 1
}

Write-Host ""
Write-Host "Verificando a instalação..."
& .\.venv\Scripts\python.exe -c "import PySide6.QtWidgets, psutil, numpy, win32gui, winrt.windows.media.ocr"
if ($LASTEXITCODE -ne 0) { throw "As dependências foram instaladas, mas não abriram corretamente." }
& .\.venv\Scripts\python.exe src\main.py --diagnostics
if ($LASTEXITCODE -ne 0) { throw "O diagnóstico do Neku falhou." }

if (-not $SemAtalho) {
    Write-Host ""
    $answer = Read-Host "Criar atalho do Neku na Área de Trabalho? (S/n)"
    if ($answer -notmatch '^[nN]') {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop "Neku.lnk"))
        $link.TargetPath = Join-Path $Root ".venv\Scripts\pythonw.exe"
        $link.Arguments = '"' + (Join-Path $Root "src\main.py") + '"'
        $link.WorkingDirectory = $Root
        $link.Description = "Neku"
        $link.Save()
        Write-Host "Atalho criado."
    }
}

Write-Host ""
Write-Host "Instalação concluída! Abra o Neku pelo atalho ou por scripts\run.bat." -ForegroundColor Green
Write-Host "Para conversas mais inteligentes, rode também scripts\instalar_modelo.bat (cerca de 240 MB)."
