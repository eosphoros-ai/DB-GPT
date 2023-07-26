#!/bin/bash

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)

bash $WORK_DIR/base/build_image.sh

bash $WORK_DIR/allinone/build_image.sh