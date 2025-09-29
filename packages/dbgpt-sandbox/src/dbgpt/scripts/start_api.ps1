# One-click start for Sandbox User API (PowerShell)
# Usage: .\scripts\start_api.ps1 -Runtime docker|podman|nerdctl|local
param(
  [string]$Runtime = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Join-Path $scriptDir ".."
Push-Location $root

Write-Host "[INFO] Project root: $PWD"

if ($Runtime) {
  $env:SANDBOX_RUNTIME = $Runtime
  Write-Host "[INFO] Prefer runtime: $env:SANDBOX_RUNTIME"
}

# Ensure Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "Python not found in PATH. Please install Python 3.10+."
  Pop-Location
  exit 1
}

# Create venv if missing
if (-not (Test-Path ".venv/Scripts/python.exe")) {
  Write-Host "[INFO] Creating virtual environment: .venv"
  python -m venv .venv
}

# Install requirements
Write-Host "[INFO] Installing requirements..."
& .venv/Scripts/python.exe -m pip install --upgrade pip
& .venv/Scripts/python.exe -m pip install -r requirements.txt

# Start server
Write-Host "[INFO] Starting API server at http://127.0.0.1:8000 ..."
Push-Location sandbox
& .venv/Scripts/python.exe -m uvicorn user_layer.service:app --host 127.0.0.1 --port 8000 --reload
$code = $LASTEXITCODE
Pop-Location

Pop-Location
exit $code
