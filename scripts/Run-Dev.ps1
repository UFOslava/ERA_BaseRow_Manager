<#
.SYNOPSIS
    Launches the ERA dev environment (backend + frontend) inside the ERA_Server WSL distro.
.DESCRIPTION
    Opens Windows Terminal windows that run the WSL-native servers:
      - Backend : Flask on :5000, MCP SSE on 0.0.0.0:8001
      - Frontend: Vite on :3000
    Windows parity for scripts/dev.sh. Falls back to plain PowerShell windows
    when Windows Terminal (wt.exe) is not installed.
.PARAMETER Mode
    all (default), backend, or frontend.
.EXAMPLE
    .\Run-Dev.ps1
    .\Run-Dev.ps1 -Mode backend
#>
param(
    [ValidateSet('all', 'backend', 'frontend')]
    [string]$Mode = 'all'
)

$ErrorActionPreference = 'Stop'

$Distro = 'ERA_Server'
$Repo   = '/home/ufoslava/projects/ERA_BaseRow_Manager'

$BackendCmd  = "cd $Repo/backend && exec ~/era-venv/bin/python run.py"
$FrontendCmd = "source ~/.nvm/nvm.sh && cd $Repo/frontend && exec npm run dev"

$HasWt = (Get-Command wt.exe -ErrorAction SilentlyContinue) -ne $null

function Launch-EraPane {
    param([string]$Title, [string]$BashCmd)

    $wsl = @('wsl.exe', '-d', $Distro, '--cd', $Repo, 'bash', '-lc', $BashCmd)

    if ($HasWt) {
        Start-Process wt.exe -ArgumentList (@('new-tab', '--title', $Title) + $wsl)
    } else {
        Start-Process powershell -ArgumentList (@('-NoExit', '-Command') + $wsl)
    }
}

Write-Host "=== ERA Dev  (WSL distro: $Distro) ===" -ForegroundColor Green

switch ($Mode) {
    'all' {
        Launch-EraPane 'ERA Backend'  $BackendCmd
        Start-Sleep -Milliseconds 800
        Launch-EraPane 'ERA Frontend' $FrontendCmd
        Write-Host "backend :5000 + MCP :8001   frontend :3000" -ForegroundColor Cyan
    }
    'backend'  { Launch-EraPane 'ERA Backend'  $BackendCmd }
    'frontend' { Launch-EraPane 'ERA Frontend' $FrontendCmd }
}

Write-Host "Stop a server with Ctrl-C in its window." -ForegroundColor Cyan
