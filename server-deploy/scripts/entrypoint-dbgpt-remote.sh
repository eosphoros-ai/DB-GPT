#!/bin/sh
set -eu
# Static export may bake API_BASE_URL=http://localhost:5670 from web/.env.local — breaks remote UI.
find /app/packages/dbgpt-app/src/dbgpt_app/static/web -type f -name '*.js' \
  -exec grep -l 'localhost:5670' {} \; 2>/dev/null \
  | while read -r f; do
      sed -i 's|http://localhost:5670||g' "$f"
    done
python3 /app/scripts/fix_db_default_outer.py || true
exec dbgpt start webserver --config "/app/configs/${DBGPT_CONFIG_FILE:-dbgpt-openrouter.toml}"
