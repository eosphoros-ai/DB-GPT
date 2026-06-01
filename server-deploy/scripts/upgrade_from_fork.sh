#!/usr/bin/env bash
# Rebuild webserver: i18n fork + OpenRouter overlay; keep MySQL/CH/pilot volumes.
set -euo pipefail

DEPLOY="${DEPLOY:-/home/algerd/dbgpt-deploy}"
SRC="${SRC:-/home/algerd/dbgpt-src}"
BRANCH="${BRANCH:-feature/i18n-ru-locale}"
OR_BRANCH="${OR_BRANCH:-feature/openrouter-multi-llm}"
REPO="${REPO:-https://github.com/algerdby/DB-GPT.git}"

cd "$DEPLOY"
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source <(sed 's/\r$//' .env)
  set +a
fi

export SRC REPO I18N_BRANCH="$BRANCH" OR_BRANCH
bash "$DEPLOY/scripts/prepare_dbgpt_src.sh"

echo "=== Build webserver (MySQL/CH volumes untouched) ==="
docker compose build webserver

echo "=== Recreate webserver ==="
docker compose up -d --force-recreate webserver

echo "=== Wait for API ==="
for i in $(seq 1 48); do
  curl -sf http://127.0.0.1:5670/api/v1/model/types >/dev/null 2>&1 && break
  sleep 5
done

echo "=== Ops patch (fmcg default DB only) ==="
docker compose exec -T webserver python3 /app/scripts/fix_db_default_outer.py || true

echo "=== Regression ==="
bash "$DEPLOY/scripts/verify_openrouter_deploy.sh" || true

echo "=== Done. Hard-refresh browser (Ctrl+Shift+R) ==="
