$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

# Versões fixas: qualquer troca precisa de novo hash conferido na fonte oficial.
$LlamaBuild = "b11829"
$LlamaUrl = "https://github.com/ggml-org/llama.cpp/releases/download/$LlamaBuild/llama-$LlamaBuild-bin-win-cpu-x64.zip"
$LlamaSha = "c534f35ce9c842f3bc224fadaecc82e1b49768f63e8320922f6dbd603f66395e"
$ModelFile = "LFM2.5-350M-Q4_K_M.gguf"
$ModelUrl = "https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/resolve/main/$ModelFile"
$ModelSha = "7e6f72643caafc9a68256686638c4d7916f2cec76d1df478d4c3ddcd95a6aed4"

function Test-Sha($Path, $Sha) {
    return (Test-Path -LiteralPath $Path) -and ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ieq $Sha)
}

function Get-Verified($Url, $Target, $Sha) {
    if (Test-Sha $Target $Sha) {
        Write-Host "  Já baixado e conferido: $(Split-Path -Leaf $Target)"
        return
    }
    $part = "$Target.part"
    & curl.exe -L --fail --retry 3 --progress-bar -o $part $Url
    if ($LASTEXITCODE -ne 0) { throw "Falha ao baixar $Url" }
    if (-not (Test-Sha $part $Sha)) {
        Remove-Item -LiteralPath $part -Force
        throw "O arquivo baixado não confere com o hash esperado e foi descartado."
    }
    Move-Item -LiteralPath $part -Destination $Target -Force
    Write-Host "  Baixado e conferido: $(Split-Path -Leaf $Target)"
}

Write-Host "Isto baixa cerca de 240 MB: o llama.cpp (23 MB) e o modelo $ModelFile (219 MB)."
Write-Host "O modelo usa a licença LFM Open License v1.0. Tudo roda só neste computador."
Write-Host ""

New-Item -ItemType Directory -Force -Path "runtime", "models" | Out-Null

Write-Host "Baixando o llama.cpp..."
$zip = Join-Path $Root "runtime\llama-$LlamaBuild.zip"
Get-Verified $LlamaUrl $zip $LlamaSha
$target = Join-Path $Root "runtime\llama"
if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
Expand-Archive -LiteralPath $zip -DestinationPath $target
if (-not (Test-Path -LiteralPath (Join-Path $target "llama-server.exe"))) {
    throw "O pacote do llama.cpp não contém llama-server.exe."
}

Write-Host "Baixando o modelo..."
Get-Verified $ModelUrl (Join-Path $Root "models\$ModelFile") $ModelSha

Write-Host ""
Write-Host "Modelo pronto! Reabra o Neku para usá-lo." -ForegroundColor Green
