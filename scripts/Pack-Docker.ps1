<#
.SYNOPSIS
    Builds and packages Docker images for ERA BaseRow Manager (Backend & Frontend).
.DESCRIPTION
    Builds the Docker container images for both the Flask backend and Vite/Nginx frontend.
    Allows optional tagging and exporting images to tar archives for distribution.
.PARAMETER Tag
    Docker image tag version (default: 'latest').
.PARAMETER ExportTar
    Switch to export built images to .tar archives in a 'dist-docker' directory.
#>
param(
    [string]$Tag = "latest",
    [switch]$ExportTar
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Check Docker availability
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Error "Docker executable not found. Please ensure Docker Desktop or Docker Engine is installed and running."
    exit 1
}

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  ERA ERP / BaseRow Manager - Docker Packager   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Image Tag: $Tag" -ForegroundColor Yellow
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray

# 1. Build Backend Image
Write-Host "`n>>> Building Backend Docker Image (era-backend:$Tag)..." -ForegroundColor Cyan
docker build -t "era-backend:$Tag" -f "$ProjectRoot\backend\Dockerfile" "$ProjectRoot\backend"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend image build failed."
    exit $LASTEXITCODE
}
Write-Host "[✓] Backend image built successfully." -ForegroundColor Green

# 2. Build Frontend Image
Write-Host "`n>>> Building Frontend Docker Image (era-frontend:$Tag)..." -ForegroundColor Cyan
docker build -t "era-frontend:$Tag" -f "$ProjectRoot\frontend\Dockerfile" "$ProjectRoot\frontend"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend image build failed."
    exit $LASTEXITCODE
}
Write-Host "[✓] Frontend image built successfully." -ForegroundColor Green

# 3. Optional Tar Export
if ($ExportTar) {
    $OutputDir = Join-Path $ProjectRoot "dist-docker"
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir | Out-Null
    }

    Write-Host "`n>>> Exporting images to $OutputDir..." -ForegroundColor Cyan
    
    $BackendTar = Join-Path $OutputDir "era-backend-$Tag.tar"
    $FrontendTar = Join-Path $OutputDir "era-frontend-$Tag.tar"

    docker save -o $BackendTar "era-backend:$Tag"
    docker save -o $FrontendTar "era-frontend:$Tag"

    Write-Host "[✓] Saved Backend archive: $BackendTar" -ForegroundColor Green
    Write-Host "[✓] Saved Frontend archive: $FrontendTar" -ForegroundColor Green
}

Write-Host "`n=================================================" -ForegroundColor Green
Write-Host " Docker packaging completed successfully!       " -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
