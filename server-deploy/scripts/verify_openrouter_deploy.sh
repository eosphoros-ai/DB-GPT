#!/usr/bin/env bash
# Smoke checks: models, native OpenRouter in image, Russian agent strings from fork.
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5670}"
FAIL=0

check() {
  if "$@"; then
    echo "OK: $*"
  else
    echo "FAIL: $*"
    FAIL=1
  fi
}

echo "=== Health ==="
check curl -sf "$BASE_URL/" >/dev/null

echo "=== Models (expect OpenRouter + LM Studio names) ==="
MODELS_JSON=$(curl -sf "$BASE_URL/api/v1/model/types" || echo '{}')
echo "$MODELS_JSON" | head -c 500
echo ""

OR_MODEL="${OPENROUTER_MODEL:-deepseek/deepseek-v4-flash}"
LM_MODEL="${LMSTUDIO_MODEL:-openai/gpt-oss-20b}"
echo "$MODELS_JSON" | grep -q "$OR_MODEL" && echo "OK: OpenRouter model listed ($OR_MODEL)" || {
  echo "WARN: $OR_MODEL not in model/types (check TOML and workers)"
  FAIL=1
}
MODEL_COUNT=$(echo "$MODELS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data') or []))" 2>/dev/null || echo 0)
if [ "${MODEL_COUNT:-0}" -ge 2 ]; then
  echo "OK: $MODEL_COUNT LLM workers registered"
elif echo "$MODELS_JSON" | grep -q "$LM_MODEL"; then
  echo "OK: secondary model $LM_MODEL listed"
else
  echo "WARN: only $MODEL_COUNT LLM(s); check LMSTUDIO_* / second [[models.llms]] and worker logs"
  FAIL=1
fi

echo "=== Native OpenRouter in container ==="
if docker exec dbgpt-webserver grep -q DBGPT_OPENROUTER_NATIVE \
  /app/packages/dbgpt-core/src/dbgpt/model/proxy/llms/chatgpt.py 2>/dev/null; then
  echo "OK: DBGPT_OPENROUTER_NATIVE in chatgpt.py"
else
  echo "FAIL: rebuild with prepare_dbgpt_src.sh + OpenRouter branch"
  FAIL=1
fi

echo "=== i18n agent API (thinking title) ==="
if docker exec dbgpt-webserver grep -q '_agent_thinking_title' \
  /app/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py 2>/dev/null; then
  echo "OK: _agent_thinking_title present (RU via _ui_lang)"
else
  echo "WARN: rebuild image from feature/i18n-ru-locale"
fi

echo "=== Datasources ==="
curl -sf "$BASE_URL/api/v2/serve/datasources" | head -c 300 || true
echo ""

exit "$FAIL"
