$ErrorActionPreference = "Stop"

py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe setup_models.py

Write-Host ""
Write-Host "Instalação concluída. Execute .\run_nero.ps1"
