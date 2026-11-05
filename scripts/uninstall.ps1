param([switch]$ManterDados)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$Scripts = Join-Path $Root ".venv\Scripts"
$PythonW = Join-Path $Scripts "pythonw.exe"

$launchers = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($Scripts, [StringComparison]::OrdinalIgnoreCase) })
if ($launchers.Count -gt 0) {
    Write-Host "O Neku está aberto e precisa ser fechado antes de desinstalar." -ForegroundColor Yellow
    $answer = Read-Host "Encerrar o Neku agora? (s/N)"
    if ($answer -notmatch '^[sS]') {
        Write-Host "Desinstalação cancelada. Nada foi alterado."
        exit 1
    }
    foreach ($p in $launchers) {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.ProcessId)" |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

# Só remove a inicialização que aponta para esta cópia do Neku.
$value = (Get-ItemProperty -Path $RunKey -Name "NekoAI" -ErrorAction SilentlyContinue).NekoAI
if ($value -and $value.IndexOf($Root, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
    Remove-ItemProperty -Path $RunKey -Name "NekoAI"
    Write-Host "Inicialização com o Windows removida."
}

$legacy = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\NekoAI.bat"
if (Test-Path -LiteralPath $legacy) {
    Remove-Item -LiteralPath $legacy
    Write-Host "Inicialização antiga (.bat) removida."
}

$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Neku.lnk"
if (Test-Path -LiteralPath $lnk) {
    $target = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath
    if ($target -ieq $PythonW) {
        Remove-Item -LiteralPath $lnk
        Write-Host "Atalho da Área de Trabalho removido."
    }
}

if (Test-Path -LiteralPath ".venv") {
    Remove-Item -LiteralPath ".venv" -Recurse -Force
    Write-Host "Ambiente virtual removido."
}

if (Test-Path -LiteralPath "runtime") {
    Remove-Item -LiteralPath "runtime" -Recurse -Force
    Write-Host "Servidor do modelo removido."
}

$models = @(Get-ChildItem -LiteralPath "models" -Filter "*.gguf*" -ErrorAction SilentlyContinue)
if ($models.Count -gt 0) {
    $models | Remove-Item -Force
    Write-Host "Modelo de linguagem removido."
}

if (-not $ManterDados) {
    Write-Host ""
    Write-Host "Suas memórias, diário, configurações e logs continuam em:"
    Write-Host "  $Root"
    Write-Host "Para apagar tudo isso de forma definitiva, digite APAGAR."
    $answer = Read-Host "Qualquer outra resposta mantém seus dados"
    if ($answer -ceq "APAGAR") {
        foreach ($folder in "data", "config", "logs") {
            if (Test-Path -LiteralPath $folder) { Remove-Item -LiteralPath $folder -Recurse -Force }
        }
        Write-Host "Dados apagados."
    }
}

Write-Host ""
Write-Host "Desinstalação concluída. Se quiser, apague a pasta do Neku manualmente." -ForegroundColor Green
