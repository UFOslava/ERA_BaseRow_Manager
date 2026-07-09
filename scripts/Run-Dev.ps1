<#
.SYNOPSIS
    Starts the development environment for both Backend and Frontend.
.DESCRIPTION
    Launches the Flask backend server and Vite frontend server in separate terminal windows.
#>

$Cwd = Get-Location

Write-Host "=== ERA BaseRow Manager Dev Orchestration ===" -ForegroundColor Green

if (-not (Test-Path "$Cwd\backend") -or -not (Test-Path "$Cwd\frontend")) {
    Write-Error "Please run this script from the workspace root containing 'backend' and 'frontend' directories."
    exit 1
}

# 1. Setup Backend virtual environment
Write-Host ">>> Setting up Python virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path "$Cwd\backend\.venv")) {
    python -m venv "$Cwd\backend\.venv"
}
& "$Cwd\backend\.venv\Scripts\pip.exe" install -r "$Cwd\backend\requirements.txt"

# 2. Setup Frontend dependencies
Write-Host ">>> Setting up Node dependencies..." -ForegroundColor Cyan
Set-Location "$Cwd\frontend"
npm install
Set-Location $Cwd

# 3. Launch Backend in a new window
Write-Host ">>> Launching Backend Dev Server (Port 5000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Cwd\backend'; & .venv\Scripts\python.exe run.py"

# 4. Launch Frontend in a new window
Write-Host ">>> Launching Frontend Dev Server (Port 3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Cwd\frontend'; npm run dev"

Write-Host "Servers launched! Monitor the spawned windows for active output." -ForegroundColor Cyan
