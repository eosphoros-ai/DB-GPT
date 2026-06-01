#!/bin/sh
set -u
echo "=== container ==="
docker inspect dbgpt-webserver --format 'image={{.Image}} created={{.Created}}'
echo "=== localhost in index js ==="
docker exec dbgpt-webserver sh -c 'grep -c localhost:5670 /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks/pages/index-*.js 2>/dev/null || true'
echo "=== sample API_BASE in index ==="
docker exec dbgpt-webserver sh -c 'grep -o "baseURL[^,]*" /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks/pages/index-*.js 2>/dev/null | head -3'
echo "=== node syntax check (first index chunk) ==="
docker exec dbgpt-webserver sh -c 'f=$(ls /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks/pages/index-*.js | head -1); node --check "$f" 2>&1 || echo SYNTAX_FAIL'
echo "=== API ==="
curl -sf http://127.0.0.1:5670/api/v1/model/types | head -c 120
echo ""
