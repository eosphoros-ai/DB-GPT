#!/bin/sh
set -eu
# Ops-only: default DB fmcg when UI does not pass database_name (not part of i18n fork).
python3 /app/scripts/fix_db_default_outer.py || true
exec dbgpt start webserver --config "/app/configs/${DBGPT_CONFIG_FILE:-dbgpt-openrouter.toml}"
