#!/bin/bash
# Восстановление модели OpenRouter, источников данных fmcg и Chroma после деплоя.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source <(sed 's/\r$//' .env)
  set +a
fi

echo "=== 1. Пересоздание webserver (последний образ) ==="
docker compose up -d --force-recreate webserver
echo "Ожидание API..."
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:5670/api/v1/chat/db/support/type >/dev/null 2>&1; then
    echo "API готов."
    break
  fi
  sleep 5
done

echo "=== 2. Chroma: очистка битых коллекций (pilot/data) ==="
docker compose exec -T webserver bash -c 'rm -rf /app/pilot/data/chroma* /app/pilot/data/*.sqlite3 2>/dev/null; ls -la /app/pilot/data/ | head -10' || true

echo "=== 3. FMCG: user_id для UI (001) ==="
python3 scripts/fix_fmcg_user_id.py

echo "=== 4. Перерегистрация ClickHouse fmcg ==="
REGISTER_MODE=force DBGPT_USER_ID=001 docker compose run --rm register-datasource

echo "=== 5. Проверка ==="
echo -n "Модели: "
curl -s http://127.0.0.1:5670/api/v1/model/types
echo
echo -n "Источники v2: "
curl -s http://127.0.0.1:5670/api/v2/serve/datasources | head -c 400
echo
echo -n "Источники v1 (чат): "
curl -s -H 'user-id: 001' http://127.0.0.1:5670/api/v1/chat/db/list | head -c 500
echo
echo "=== restore_server_runtime: готово ==="
