#!/bin/sh
HTML=$(curl -sf http://127.0.0.1:5670/)
echo "=== buildId in HTML ==="
echo "$HTML" | tr '"' '\n' | grep '_buildManifest\|_ssgManifest' | head -4
echo "=== manifest dirs on disk ==="
ls -d /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/*/
echo "=== index in each manifest ==="
for d in /app/packages/dbgpt-app/src/dbgpt_app/static/web/_next/static/*/; do
  if test -f "${d}_buildManifest.js"; then
    echo "-- $d"
    grep -o 'pages/index-[^"]*' "${d}_buildManifest.js" | head -1
  fi
done
