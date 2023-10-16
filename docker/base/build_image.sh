#!/bin/bash

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)

BASE_IMAGE_DEFAULT="nvidia/cuda:11.8.0-runtime-ubuntu22.04"
BASE_IMAGE_DEFAULT_CPU="ubuntu:22.04"

BASE_IMAGE=$BASE_IMAGE_DEFAULT
IMAGE_NAME="eosphorosai/dbgpt"
IMAGE_NAME_ARGS=""

# zh: https://pypi.tuna.tsinghua.edu.cn/simple
PIP_INDEX_URL="https://pypi.org/simple"
# en or zh
LANGUAGE="en"
BUILD_LOCAL_CODE="true"
LOAD_EXAMPLES="true"
BUILD_NETWORK=""
DB_GPT_INSTALL_MODEL="default"

usage () {
    echo "USAGE: $0 [--base-image nvidia/cuda:11.8.0-runtime-ubuntu22.04] [--image-name db-gpt]"
    echo "  [-b|--base-image base image name] Base image name"
    echo "  [-n|--image-name image name] Current image name, default: db-gpt"
    echo "  [-i|--pip-index-url pip index url] Pip index url, default: https://pypi.org/simple"
    echo "  [--language en or zh] You language, default: en"
    echo "  [--build-local-code true or false] Whether to use the local project code to package the image, default: true"
    echo "  [--load-examples true or false] Whether to load examples to default database default: true"
    echo "  [--network network name] The network of docker build"
    echo "  [--install-mode mode name] Installation mode name, default: default, If you completely use openai's service, you can set the mode name to 'openai'"
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
        IMAGE_NAME_ARGS="$2"
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
        --network)
        BUILD_NETWORK=" --network $2 "
        shift # past argument
        shift # past value
        ;;
        -h|--help)
        help="true"
        shift
        ;;
        --install-mode)
        DB_GPT_INSTALL_MODEL="$2"
        shift # past argument
        shift # past value
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

if [ "$DB_GPT_INSTALL_MODEL" != "default" ]; then
    IMAGE_NAME="$IMAGE_NAME-$DB_GPT_INSTALL_MODEL"
    echo "install mode is not 'default', set image name to: ${IMAGE_NAME}"
fi

if [ -z "$IMAGE_NAME_ARGS" ]; then
    if [ "$DB_GPT_INSTALL_MODEL" == "openai" ]; then 
        # Use cpu image
        BASE_IMAGE=$BASE_IMAGE_DEFAULT_CPU
    fi
else
    # User input image is not empty
    BASE_IMAGE=$IMAGE_NAME_ARGS
fi

echo "Begin build docker image, base image: ${BASE_IMAGE}, target image name: ${IMAGE_NAME}"

docker build $BUILD_NETWORK \
    --build-arg BASE_IMAGE=$BASE_IMAGE \
    --build-arg PIP_INDEX_URL=$PIP_INDEX_URL \
    --build-arg LANGUAGE=$LANGUAGE \
    --build-arg BUILD_LOCAL_CODE=$BUILD_LOCAL_CODE \
    --build-arg LOAD_EXAMPLES=$LOAD_EXAMPLES \
    --build-arg DB_GPT_INSTALL_MODEL=$DB_GPT_INSTALL_MODEL \
    -f Dockerfile \
    -t $IMAGE_NAME $WORK_DIR/../../
