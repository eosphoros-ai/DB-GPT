#!/bin/bash

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)

IMAGE_NAME="eosphorosai/dbgpt-allinone"

docker build -f Dockerfile -t $IMAGE_NAME $WORK_DIR/../../