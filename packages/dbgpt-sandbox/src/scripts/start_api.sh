#!/usr/bin/env bash
# One-click start for Sandbox User API (Linux/macOS)
# Usage:
#   ./scripts/start_api.sh                 # 自动创建 .venv 并安装依赖后启动
#   ./scripts/start_api.sh docker          # 强制选择 Docker 作为运行时
#   SANDBOX_RUNTIME=local ./scripts/start_api.sh  # 通过环境变量指定

set -Eeuo pipefail

RUNTIME_ARG="${1:-}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

echo "[INFO] Project root: $PWD"

# Prefer runtime via first argument (optional)
if [[ -n "$RUNTIME_ARG" ]]; then
  export SANDBOX_RUNTIME="$RUNTIME_ARG"
  echo "[INFO] Prefer runtime: $SANDBOX_RUNTIME"
fi

# Detect Python 3
PY_BIN="$(command -v python3 || true)"
if [[ -z "$PY_BIN" ]]; then
  PY_BIN="$(command -v python || true)"
fi
if [[ -z "$PY_BIN" ]]; then
  echo "[ERROR] Python 3 not found in PATH. Please install Python 3.10+." >&2
  exit 1
fi

# Ensure venv
VENV_PY=".venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "[INFO] Creating virtual environment: .venv"
  "$PY_BIN" -m venv .venv
fi

# Install requirements
echo "[INFO] Installing requirements..."
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r requirements.txt

# Start server
echo "[INFO] Starting API server at http://127.0.0.1:8000 ..."
cd sandbox
exec "$VENV_PY" -m uvicorn user_layer.service:app --host 127.0.0.1 --port 8000 --reload
