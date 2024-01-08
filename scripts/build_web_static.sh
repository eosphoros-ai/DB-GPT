#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)
WORK_DIR="$WORK_DIR/.."

cd $WORK_DIR/web

source_env=".env"
tmp_env=".env.copy"

if [ -e "$source_env" ]; then
  cp "$source_env" "$tmp_env"
  rm -rf "$source_env"
else
  echo "Do not find .env"
fi

npm install
npm run build

rm -rf ../dbgpt/app/static/*

cp -R ../web/out/* ../dbgpt/app/static

if [ -e "$tmp_env" ]; then
  cp "$tmp_env" "$source_env" 
  rm -rf "$tmp_env"
fi