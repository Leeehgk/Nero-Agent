param(
    [int]$Port = 1234,
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

function Find-LmsCli {
    $command = Get-Command "lms" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidate = Join-Path $env:USERPROFILE ".lmstudio\bin\lms.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    return $null
}

function Test-LmStudioServer {
    param([int]$ServerPort)

    try {
        Invoke-RestMethod `
            -Uri "http://127.0.0.1:$ServerPort/api/v1/models" `
            -Method Get `
            -TimeoutSec 1 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

$lms = Find-LmsCli
if (-not $lms) {
    Write-Warning "CLI do LM Studio não encontrado; não há serviço para encerrar."
    return
}

if (Test-LmStudioServer -ServerPort $Port) {
    Write-Host "Descarregando os modelos do Nero..."
    & $lms unload --all

    Write-Host "Parando a API local do LM Studio..."
    & $lms server stop
}

Write-Host "Encerrando o serviço llmster..."
& $lms daemon down

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    if (-not (Test-LmStudioServer -ServerPort $Port)) {
        Write-Host "LM Studio encerrado e memória liberada." `
            -ForegroundColor Green
        return
    }
    Start-Sleep -Milliseconds 250
} while ((Get-Date) -lt $deadline)

throw "A API local ainda responde na porta $Port após $TimeoutSeconds segundos."
