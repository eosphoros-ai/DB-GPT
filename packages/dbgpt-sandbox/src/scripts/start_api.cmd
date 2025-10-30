@echo off
setlocal enabledelayedexpansion

REM One-click start for Sandbox User API (Windows cmd.exe)
REM Usage: scripts\start_api.cmd [docker|podman|nerdctl|local]

set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%.."
pushd "%ROOT%" >nul

echo [INFO] Project root: %CD%

REM Optional: runtime preference from arg1
if "%~1"=="" (
  set "SANDBOX_RUNTIME="
) else (
  set "SANDBOX_RUNTIME=%~1"
  echo [INFO] Prefer runtime: %SANDBOX_RUNTIME%
)

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Please install Python 3.10+.
  popd >nul
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating virtual environment: .venv
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create venv.
    popd >nul
    exit /b 1
  )
)

echo [INFO] Upgrading pip and installing requirements...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [WARN] pip upgrade failed, continue...
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed.
  popd >nul
  exit /b 1
)

echo [INFO] Starting API server at http://127.0.0.1:8000 ...
if not "%SANDBOX_RUNTIME%"=="" (
  set "SANDBOX_RUNTIME=%SANDBOX_RUNTIME%"
)
REM 先进入 sandbox 目录再运行
pushd sandbox >nul
".venv\Scripts\python.exe" -m uvicorn user_layer.service:app --host 127.0.0.1 --port 8000 --reload
set "EXITCODE=%ERRORLEVEL%"
popd >nul

popd >nul
exit /b %EXITCODE%
