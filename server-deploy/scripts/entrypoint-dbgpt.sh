#!/bin/sh
set -eu
python3 /app/scripts/patch_openrouter_provider.py
python3 /app/scripts/fix_db_default_outer.py || true
python3 /app/scripts/repair_agentic_api_syntax.py || true
python3 /app/scripts/patch_agentic_ru_strings.py || true
exec dbgpt start webserver --config "/app/configs/${DBGPT_CONFIG_FILE:-dbgpt-docker.toml}"
