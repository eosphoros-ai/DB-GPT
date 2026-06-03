#!/bin/sh
# One-shot: strip baked localhost API base from running webserver static files.
set -eu
docker exec dbgpt-webserver sh -c '
  n=0
  for f in $(find /app/packages/dbgpt-app/src/dbgpt_app/static/web -type f -name "*.js" 2>/dev/null); do
    if grep -q "localhost:5670" "$f" 2>/dev/null; then
      sed -i "s|http://localhost:5670||g" "$f"
      n=$((n+1))
    fi
  done
  echo "patched_files=$n"
'
