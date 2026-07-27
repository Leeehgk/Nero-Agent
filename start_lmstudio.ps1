param(
    [int]$Port = 1234,
    [int]$TimeoutSeconds = 30
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

    throw @"
CLI do LM Studio não encontrado.
Instale ou abra o LM Studio e confirme que o comando 'lms' está disponível.
"@
}

function Test-LmStudioServer {
    param([int]$ServerPort)

    try {
        $response = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$ServerPort/api/v1/models" `
            -Method Get `
            -TimeoutSec 2
        return $null -ne $response.models
    }
    catch {
        return $false
    }
}

if (Test-LmStudioServer -ServerPort $Port) {
    Write-Host "LM Studio já está acessível em http://127.0.0.1:$Port" `
        -ForegroundColor Green
    return
}

$lms = Find-LmsCli
Write-Host "Iniciando o serviço local do LM Studio..."
& $lms daemon up

Write-Host "Iniciando o servidor em 127.0.0.1:$Port..."
& $lms server start --port $Port --bind "127.0.0.1"

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    if (Test-LmStudioServer -ServerPort $Port) {
        Write-Host "LM Studio pronto em http://127.0.0.1:$Port" `
            -ForegroundColor Green
        return
    }
    Start-Sleep -Milliseconds 300
} while ((Get-Date) -lt $deadline)

throw @"
O serviço foi iniciado, mas a API não respondeu em $TimeoutSeconds segundos.
Execute '$lms status' para consultar o estado do LM Studio.
"@
