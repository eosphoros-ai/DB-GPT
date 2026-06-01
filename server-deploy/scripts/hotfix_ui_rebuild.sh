#!/bin/sh
set -eu
cd /home/algerd/dbgpt-deploy
echo "=== build webserver (clean _next in image) ==="
docker compose build --no-cache webserver
echo "=== recreate ==="
docker compose up -d --force-recreate webserver
echo "=== wait health ==="
for i in $(seq 1 40); do
  curl -sf http://127.0.0.1:5670/api/v1/model/types >/dev/null 2>&1 && break
  sleep 5
done
echo "=== verify single index chunk set ==="
docker exec dbgpt-webserver ls /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks/pages/index-*.js 2>/dev/null | wc -l
docker exec dbgpt-webserver grep -rl localhost:5670 /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks 2>/dev/null | wc -l
echo "=== done ==="
