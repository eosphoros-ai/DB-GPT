#!/bin/sh
set -eu

WEB_DIR="${1:-/build/web}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

echo "=== build_web_static: web=$WEB_DIR ==="
python3 "$SCRIPT_DIR/prepare_web_deploy.py" "$WEB_DIR"

cd "$WEB_DIR"
corepack enable
corepack prepare yarn@1.22.22 --activate

# Next.js loads .env.local — must not bake localhost into static export for remote access.
ENV_BACKUP_DIR=""
for f in .env .env.local .env.development .env.production; do
  if [ -f "$f" ]; then
    if [ -z "$ENV_BACKUP_DIR" ]; then
      ENV_BACKUP_DIR=".env.build.bak.d"
      mkdir -p "$ENV_BACKUP_DIR"
    fi
    cp "$f" "$ENV_BACKUP_DIR/"
    rm -f "$f"
  fi
done

export NODE_OPTIONS="${NODE_OPTIONS:---max_old_space_size=8192}"
export NEXT_TELEMETRY_DISABLED=1
# Relative API URLs: same host as UI (192.168.x.x:5670), not developer localhost.
export API_BASE_URL=""

echo "yarn install..."
yarn install --network-timeout 600000

rm -rf out .next
echo "yarn compile..."
yarn compile

if [ -n "$ENV_BACKUP_DIR" ] && [ -d "$ENV_BACKUP_DIR" ]; then
  for f in .env .env.local .env.development .env.production; do
    [ -f "$ENV_BACKUP_DIR/$f" ] && mv "$ENV_BACKUP_DIR/$f" .
  done
  rmdir "$ENV_BACKUP_DIR" 2>/dev/null || true
fi

if [ ! -d out ] || [ -z "$(ls -A out 2>/dev/null)" ]; then
  echo "build_web_static: out пуст"
  exit 1
fi
echo "build_web_static: OK, files=$(find out -type f | wc -l)"
