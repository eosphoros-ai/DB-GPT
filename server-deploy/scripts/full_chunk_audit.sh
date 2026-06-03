#!/bin/sh
set -u
BASE=http://127.0.0.1:5670
STATIC=/app/packages/dbgpt-app/src/dbgpt_app/static
HTML=$(curl -sf "$BASE/")
echo "=== MISSING CHUNKS (404) ==="
missing=0
for path in $(echo "$HTML" | tr '"' '\n' | grep '_next/static/chunks.*\.js'); do
  rel="${path#/}"
  f="$STATIC/$rel"
  if ! test -f "$f"; then
    echo "MISSING $path"
    missing=$((missing + 1))
  fi
done
echo "missing_count=$missing"
echo "=== BUILD MANIFEST index ==="
grep -o 'static/chunks/pages/index-[^"]*' "$STATIC/web/_next/static"/*/_buildManifest.js 2>/dev/null | head -3
echo "=== index chunks on disk ==="
ls "$STATIC/web/_next/static/chunks/pages/index-"*.js 2>/dev/null
echo "=== _app in HTML ==="
echo "$HTML" | tr '"' '\n' | grep '_app-' | head -1
