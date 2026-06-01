#!/bin/bash
# Полное восстановление: модель OpenRouter, источники, диалоги, Chroma, новый UI.
set -euo pipefail
DEPLOY="/home/algerd/dbgpt-deploy"
SRC="/home/algerd/dbgpt-src"
cd "$DEPLOY"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source <(sed 's/\r$//' .env)
  set +a
fi

echo "=== 1. Sync dbgpt-src + сборка webserver ==="
bash "$DEPLOY/scripts/prepare_dbgpt_src.sh"
docker compose build webserver

echo "=== 2. Пересоздание webserver ==="
docker compose up -d --force-recreate webserver

echo "=== 3. Ожидание API (до 3 мин) ==="
for i in $(seq 1 36); do
  if curl -sf http://127.0.0.1:5670/api/v1/chat/db/support/type >/dev/null 2>&1; then
    echo "API готов (${i}0s)"
    break
  fi
  sleep 5
done

echo "=== 4. Ops patch (fmcg default DB) ==="
docker compose exec -T webserver python3 /app/scripts/fix_db_default_outer.py || true
bash "$DEPLOY/scripts/verify_openrouter_deploy.sh" || true

echo "=== 5. Chroma: сброс битых коллекций ==="
docker compose exec -T webserver bash -c 'rm -rf /app/pilot/data/chroma /app/pilot/data/chroma.sqlite3 2>/dev/null; true'

echo "=== 6. FMCG user_id + перерегистрация ==="
python3 scripts/fix_fmcg_user_id.py
REGISTER_MODE=force DBGPT_USER_ID=001 docker compose run --rm register-datasource

echo "=== 7. ClickHouse COMMENT ==="
if [ -f scripts/post_deploy_fmcg.sh ]; then
  chmod +x scripts/post_deploy_fmcg.sh
  REGISTER_MODE=refresh ./scripts/post_deploy_fmcg.sh 2>&1 | tail -8
fi

echo "=== 8. Проверка ==="
echo "--- Модели ---"
curl -s http://127.0.0.1:5670/api/v1/model/types
echo
echo "--- Источники (v2) ---"
curl -s http://127.0.0.1:5670/api/v2/serve/datasources | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print([x['db_name'] for x in d])" 2>/dev/null || true
echo "--- Диалоги ---"
curl -s http://127.0.0.1:5670/api/v1/chat/dialogue/list | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print('count=',len(d))" 2>/dev/null || true
echo "--- Навыки ---"
curl -s http://127.0.0.1:5670/api/v1/skills/list | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print([x['id'] for x in d])" 2>/dev/null || true
echo "=== Готово: http://$(hostname -I | awk '{print $1}'):5670 ==="
echo "В браузере: Ctrl+Shift+R; при необходимости: localStorage.setItem('__db_gpt_lng_key','ru'); location.reload();"
