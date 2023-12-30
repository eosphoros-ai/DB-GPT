#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)
WORK_DIR="$WORK_DIR/.."

cd $WORK_DIR/web

npm install
npm run build

rm -rf ../dbgpt/app/static/*

cp -R ../web/out/* ../dbgpt/app/static