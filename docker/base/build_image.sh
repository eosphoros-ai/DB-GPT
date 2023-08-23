#!/bin/bash

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)

BASE_IMAGE="nvidia/cuda:11.8.0-runtime-ubuntu22.04"
IMAGE_NAME="eosphorosai/dbgpt"
# zh: https://pypi.tuna.tsinghua.edu.cn/simple
PIP_INDEX_URL="https://pypi.org/simple"
# en or zh
LANGUAGE="en"
BUILD_LOCAL_CODE="false"
LOAD_EXAMPLES="true"

usage () {
    echo "USAGE: $0 [--base-image nvidia/cuda:11.8.0-runtime-ubuntu22.04] [--image-name db-gpt]"
    echo "  [-b|--base-image base image name] Base image name"
    echo "  [-n|--image-name image name] Current image name, default: db-gpt"
    echo "  [-i|--pip-index-url pip index url] Pip index url, default: https://pypi.org/simple"
    echo "  [--language en or zh] You language, default: en"
    echo "  [--build-local-code true or false] Whether to use the local project code to package the image, default: false"
    echo "  [--load-examples true or false] Whether to load examples to default database default: true"
    echo "  [-h|--help] Usage message"
}

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -b|--base-image)
        BASE_IMAGE="$2"
        shift # past argument
        shift # past value
        ;;
        -n|--image-name)
        IMAGE_NAME="$2"
        shift # past argument
        shift # past value
        ;;
        -i|--pip-index-url)
        PIP_INDEX_URL="$2"
        shift
        shift
        ;;
        --language)
        LANGUAGE="$2"
        shift
        shift
        ;;
        --build-local-code)
        BUILD_LOCAL_CODE="$2"
        shift
        shift
        ;;
        --load-examples)
        LOAD_EXAMPLES="$2"
        shift
        shift
        ;;
        -h|--help)
        help="true"
        shift
        ;;
        *)
        usage
        exit 1
        ;;
    esac
done

if [[ $help ]]; then
    usage
    exit 0
fi

docker build \
    --build-arg BASE_IMAGE=$BASE_IMAGE \
    --build-arg PIP_INDEX_URL=$PIP_INDEX_URL \
    --build-arg LANGUAGE=$LANGUAGE \
    --build-arg BUILD_LOCAL_CODE=$BUILD_LOCAL_CODE \
    --build-arg LOAD_EXAMPLES=$LOAD_EXAMPLES \
    -f Dockerfile \
    -t $IMAGE_NAME $WORK_DIR/../../
