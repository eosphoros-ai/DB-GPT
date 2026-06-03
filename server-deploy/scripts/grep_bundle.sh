#!/bin/sh
WEB=/app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks
echo "localhost count:"
grep -r localhost:5670 "$WEB" 2>/dev/null | wc -l
echo "undefined API:"
grep -r 'localhost:5670\|API_BASE_URL.*undefined' "$WEB/pages" 2>/dev/null | head -3
IDX=$(ls "$WEB"/pages/index-*.js 2>/dev/null | head -1)
echo "index file: $IDX"
grep -o 'baseURL:"[^"]*"' "$IDX" 2>/dev/null | head -1
grep -o 'API_BASE_URL[^,}]*' "$IDX" 2>/dev/null | head -3
