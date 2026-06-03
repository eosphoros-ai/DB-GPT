#!/bin/bash
# Чистый деплой: новый ru-перевод в образе, старые MySQL/CH/pilot volumes, без i18n-патчей.
set -euo pipefail
DEPLOY="/home/algerd/dbgpt-deploy"
cd "$DEPLOY"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source <(sed 's/\r$//' .env)
  set +a
fi

echo "=== Удаление лишних файлов из web (если попали в pages/) ==="
rm -f /home/algerd/dbgpt-src/web/pages/storage.ts /home/algerd/dbgpt-src/web/pages/ctx-axios.ts 2>/dev/null || true

echo "=== Архив старых patch-скриптов ==="
mkdir -p scripts/legacy-patches-disabled
for f in scripts/patch_ru_full.py scripts/patch_agentic_ru.py scripts/patch_web_source_ru.py \
  scripts/apply_zh_ru_patch.py scripts/patch_bundle_*.py scripts/patch_moment_ru.py \
  scripts/patch_ui_default_ru.py scripts/patch_i18n_t_calls.py scripts/patch_cache_bust.py \
  scripts/patch_construct_ui_ru.py scripts/patch_antd_locale_ru.py scripts/patch_create_app_modal.py \
  scripts/patch_timezone_ru.py scripts/patch_team_mode_backend.py scripts/patch_agent_ui_fixes.py \
  scripts/patch_csv_data_analysis_ru.py scripts/patch_react_agent_ru.py scripts/patch_agentic_react_ru.py \
  scripts/prepare_web_ru_build.py scripts/build_web_static_ru.sh; do
  [ -f "$f" ] && mv -f "$f" scripts/legacy-patches-disabled/ 2>/dev/null || true
done
rm -rf locales 2>/dev/null || true

echo "=== Sync dbgpt-src (i18n + OpenRouter overlay) ==="
export SRC="${SRC:-/home/algerd/dbgpt-src}"
bash scripts/prepare_dbgpt_src.sh

echo "=== Сборка webserver (5–15 мин) ==="
docker compose build --no-cache webserver

echo "=== Перезапуск без пересоздания MySQL/ClickHouse ==="
docker compose up -d --force-recreate webserver

echo "=== Ожидание API ==="
for i in $(seq 1 40); do
  curl -sf http://127.0.0.1:5670/api/v1/chat/db/support/type >/dev/null 2>&1 && break
  sleep 5
done

echo "=== Runtime (только fmcg default DB) ==="
docker compose exec -T webserver python3 /app/scripts/fix_db_default_outer.py || true

echo "=== Chroma: сброс битых коллекций ==="
docker compose exec -T webserver bash -c 'rm -rf /app/pilot/data/chroma /app/pilot/data/chroma.sqlite3 2>/dev/null; true'

echo "=== Переподключение fmcg в DB-GPT ==="
python3 scripts/fix_fmcg_user_id.py
REGISTER_MODE=refresh DBGPT_USER_ID=001 docker compose --profile init-data run --rm register-datasource

if [ -f scripts/post_deploy_fmcg.sh ]; then
  chmod +x scripts/post_deploy_fmcg.sh
  REGISTER_MODE=refresh ./scripts/post_deploy_fmcg.sh || true
fi

echo "=== Проверка ==="
echo "Модели:" && curl -s http://127.0.0.1:5670/api/v1/model/types
echo ""
echo "БД:" && curl -s http://127.0.0.1:5670/api/v2/serve/datasources | python3 -c "import sys,json; print([x['db_name'] for x in json.load(sys.stdin)['data']])" 2>/dev/null || true
echo "Диалоги:" && curl -s http://127.0.0.1:5670/api/v1/chat/dialogue/list | python3 -c "import sys,json; print('count=',len(json.load(sys.stdin)['data']))" 2>/dev/null || true
echo "Навыки:" && curl -s http://127.0.0.1:5670/api/v1/skills/list | python3 -c "import sys,json; print([x['id'] for x in json.load(sys.stdin)['data']])" 2>/dev/null || true
echo "=== Готово: http://$(hostname -I | awk '{print $1}'):5670 (Ctrl+Shift+R в браузере) ==="
