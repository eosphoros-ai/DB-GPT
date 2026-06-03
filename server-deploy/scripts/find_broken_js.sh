#!/bin/sh
WEB=/app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks
echo "=== localhost refs ==="
grep -rl 'localhost:5670' "$WEB" 2>/dev/null | wc -l
echo "=== suspicious patterns (sed damage) ==="
grep -rlE '""\+""|baseURL:""|,\s*,|undefined/api' "$WEB" 2>/dev/null | head -10
echo "=== check key chunks exist ==="
for f in pages/_app-8a5f76f00c998cce.js pages/index-7ee0b02b2f7cb73d.js framework-8b06d32cbb857e0e.js main-6c4c7f5b8c9b1320.js; do
  test -f "$WEB/$f" && echo OK "$f" || echo MISSING "$f"
done
echo "=== HTML references vs disk ==="
HTML=$(curl -sf http://127.0.0.1:5670/)
echo "$HTML" | tr '"' '\n' | grep '_next/static/chunks.*\.js' | while read -r p; do
  rel="${p#/}"
  if test -f "/app/packages/dbgpt-app/src/dbgpt_app/static/$rel"; then
    echo "OK $p"
  else
    echo "MISSING $p"
  fi
done | head -20
