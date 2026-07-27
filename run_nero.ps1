$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$serverScript = Join-Path $PSScriptRoot "start_lmstudio.ps1"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente não encontrado. Execute .\install.ps1 primeiro."
}

& $serverScript
& $python (Join-Path $PSScriptRoot "app.py")
