# Single safe KIC Windows local verification (synthetic test data only).
# Usage: powershell -ExecutionPolicy Bypass -File .\verify_local.ps1 [-Full]
param([switch]$Full)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        Write-Error "Python 3.11+ not found on PATH."
        exit 2
    }
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $params = @("-B", "-m", "scripts.verify_local")
    if ($Full) { $params += "--full" }
    & $python.Source @params
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
