<#
.SYNOPSIS
    Runs test suites for both Backend and Frontend.
.DESCRIPTION
    Runs pytest with coverage for the backend and vitest for the frontend.
#>

$Cwd = Get-Location

Write-Host "=== Running Backend Tests (pytest) ===" -ForegroundColor Cyan
if (-not (Test-Path "$Cwd\backend\.venv")) {
    Write-Host "Creating Python Virtual Environment for tests..." -ForegroundColor Yellow
    python -m venv "$Cwd\backend\.venv"
    & "$Cwd\backend\.venv\Scripts\pip.exe" install -r "$Cwd\backend\requirements.txt"
}

# Run pytest inside venv
& "$Cwd\backend\.venv\Scripts\pytest.exe" "$Cwd\backend\tests" --cov="$Cwd\backend\app" --cov-report=term-missing
$BackendResult = $LASTEXITCODE

Write-Host "`n=== Running Frontend Tests (vitest) ===" -ForegroundColor Cyan
if (-not (Test-Path "$Cwd\frontend\node_modules")) {
    Write-Host "Installing frontend node_modules..." -ForegroundColor Yellow
    Set-Location "$Cwd\frontend"
    npm install
    Set-Location $Cwd
}

Set-Location "$Cwd\frontend"
npm run test
$FrontendResult = $LASTEXITCODE
Set-Location $Cwd

Write-Host "`n=== Test Execution Summary ===" -ForegroundColor Green
if ($BackendResult -eq 0) {
    Write-Host "Backend Tests: PASSED" -ForegroundColor Green
} else {
    Write-Host "Backend Tests: FAILED (Code $BackendResult)" -ForegroundColor Red
}

if ($FrontendResult -eq 0) {
    Write-Host "Frontend Tests: PASSED" -ForegroundColor Green
} else {
    Write-Host "Frontend Tests: FAILED (Code $FrontendResult)" -ForegroundColor Red
}

if ($BackendResult -eq 0 -and $FrontendResult -eq 0) {
    Write-Host "`nAll test suites passed successfully!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`nOne or more test suites failed." -ForegroundColor Red
    exit 1
}
