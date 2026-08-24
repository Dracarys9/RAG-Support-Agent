$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "The project environment is missing. Run this once first:" -ForegroundColor Yellow
    Write-Host "py -m venv .venv"
    exit 1
}

Write-Host "Preparing Aster & Row support chat..." -ForegroundColor Cyan
& $python -m pip install -e . --disable-pip-version-check --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency installation failed. Check the message above." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Opening http://127.0.0.1:5000" -ForegroundColor Green
Start-Process "http://127.0.0.1:5000"
Write-Host "The chat is running. Press Ctrl+C to stop it." -ForegroundColor DarkGray
& $python -m rag_support_agent.web_app
