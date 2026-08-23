<#
.SYNOPSIS
    Orchestrates Docker container builds and launches via Docker Compose.
.DESCRIPTION
    Checks if Docker command is available, checks/initializes .env configuration,
    and runs docker compose up with build.
.PARAMETER Detached
    Run containers in background (default: true).
.PARAMETER Down
    Stops and removes active containers.
#>
param(
    [switch]$Detached = $true,
    [switch]$Down
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Check if Docker is in PATH
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Error "Docker executable not found. Please ensure Docker Desktop is installed and running."
    exit 1
}

Set-Location $ProjectRoot

if ($Down) {
    Write-Host ">>> Stopping ERA BaseRow Manager Docker containers..." -ForegroundColor Yellow
    docker compose down
    exit 0
}

Write-Host "=== ERA BaseRow Manager Docker Orchestration ===" -ForegroundColor Green

# Check for .env file
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "No .env found. Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item -Path $EnvExample -Destination $EnvFile
    } else {
        Write-Warning ".env file not found. Containers will use default environment variables."
    }
}

# 1. Build and bring up containers
Write-Host ">>> Running docker compose up --build..." -ForegroundColor Cyan
if ($Detached) {
    docker compose up --build -d
} else {
    docker compose up --build
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDocker containers started successfully!" -ForegroundColor Green
    Write-Host "Frontend: http://localhost:3000" -ForegroundColor Gray
    Write-Host "Backend:  http://localhost:5000" -ForegroundColor Gray
    Write-Host "Use 'powershell .\scripts\Run-Docker.ps1 -Down' or 'docker compose down' to stop the containers." -ForegroundColor Gray
} else {
    Write-Error "Failed to start Docker containers."
    exit $LASTEXITCODE
}
