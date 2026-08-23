<#
.SYNOPSIS
    Initializes and synchronizes the Baserow database schema for ERA BaseRow Manager.
.DESCRIPTION
    Checks Baserow connectivity, discovers existing tables, synchronizes missing schema,
    seeds default values, and auto-populates table IDs into local .env files.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

# Use venv Python if available, otherwise system Python
$PythonExe = "python"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
}

Write-Host "=== ERA BaseRow Manager - Baserow Schema Initializer ===" -ForegroundColor Cyan
Set-Location $BackendDir

& $PythonExe -m app.baserow_init
$ExitCode = $LASTEXITCODE

Set-Location $ProjectRoot
exit $ExitCode
