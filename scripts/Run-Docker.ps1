<#
.SYNOPSIS
    Orchestrates Docker container builds and launches.
.DESCRIPTION
    Checks if Docker command is available, builds containers, and runs docker compose.
#>

$Cwd = Get-Location

# Check if Docker is in PATH
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Error "Docker executable not found. Please ensure Docker Desktop is installed and running."
    exit 1
}

Write-Host "=== ERA BaseRow Manager Docker Orchestration ===" -ForegroundColor Green

# 1. Build and bring up containers
Write-Host ">>> Running docker-compose build and up..." -ForegroundColor Cyan
docker compose up --build -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDocker containers started successfully!" -ForegroundColor Green
    Write-Host "Frontend: http://localhost:3000" -ForegroundColor Gray
    Write-Host "Backend:  http://localhost:5000" -ForegroundColor Gray
    Write-Host "Use 'docker compose down' to stop the containers." -ForegroundColor Gray
} else {
    Write-Error "Failed to start Docker containers."
    exit $LASTEXITCODE
}
