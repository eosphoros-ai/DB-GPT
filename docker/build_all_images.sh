#!/bin/bash

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)

bash $WORK_DIR/base/build_image.sh "$@"

if [ 0 -ne $? ]; then
    ehco "Error: build base image failed"
    exit 1
fi

bash $WORK_DIR/allinone/build_image.sh