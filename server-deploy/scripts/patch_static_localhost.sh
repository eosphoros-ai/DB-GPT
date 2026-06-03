#!/bin/sh
set -eu
n=0
for f in $(find /app/packages/dbgpt-app/src/dbgpt_app/static/web -type f -name '*.js' 2>/dev/null); do
  if grep -q 'localhost:5670' "$f" 2>/dev/null; then
    sed -i 's|http://localhost:5670||g' "$f"
    n=$((n + 1))
  fi
done
echo "patched=$n"
grep -c 'localhost:5670' /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/chunks/pages/index-*.js 2>/dev/null || echo "index_ok=0"
