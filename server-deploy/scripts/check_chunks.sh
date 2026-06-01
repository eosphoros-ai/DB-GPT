#!/bin/sh
HTML=$(curl -sf http://127.0.0.1:5670/)
echo "$HTML" | tr '"' '\n' | grep '_next/static/chunks' | head -12
echo "---"
for path in $(echo "$HTML" | tr '"' '\n' | grep '_next/static/chunks.*\.js' | head -8); do
  code=$(curl -sf -o /dev/null -w "%{http_code}" "http://127.0.0.1:5670/$path")
  echo "$code $path"
done
