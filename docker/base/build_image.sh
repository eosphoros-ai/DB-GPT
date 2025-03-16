#!/bin/bash

SCRIPT_LOCATION=$0
cd "$(dirname "$SCRIPT_LOCATION")"
WORK_DIR=$(pwd)

# Base image definitions
CUDA_BASE_IMAGE="nvidia/cuda:12.4.0-devel-ubuntu22.04"
CPU_BASE_IMAGE="ubuntu:22.04"

# Define installation mode configurations (macOS-compatible format)

# Common mode configurations
DEFAULT_PROXY_EXTRAS="base,proxy_openai,rag,graph_rag,storage_chromadb,dbgpts,proxy_ollama,proxy_zhipuai,proxy_anthropic,proxy_qianfan,proxy_tongyi"
DEFAULT_CUDA_EXTRAS="${DEFAULT_PROXY_EXTRAS},cuda121,hf,quant_bnb,flash_attn,quant_awq"

# Set default options for each installation mode
# Default mode
DEFAULT_BASE_IMAGE=$CUDA_BASE_IMAGE
DEFAULT_EXTRAS=$DEFAULT_CUDA_EXTRAS
DEFAULT_ENV_VARS=""

# OpenAI mode
OPENAI_BASE_IMAGE=$CPU_BASE_IMAGE
OPENAI_EXTRAS="${DEFAULT_PROXY_EXTRAS}"
OPENAI_ENV_VARS=""

# VLLM mode
VLLM_BASE_IMAGE=$CUDA_BASE_IMAGE
VLLM_EXTRAS="$DEFAULT_CUDA_EXTRAS,vllm"
VLLM_ENV_VARS=""

# LLAMA-CPP mode
LLAMA_CPP_BASE_IMAGE=$CUDA_BASE_IMAGE
LLAMA_CPP_EXTRAS="$DEFAULT_CUDA_EXTRAS,llama_cpp,llama_cpp_server"
LLAMA_CPP_ENV_VARS="CMAKE_ARGS=\"-DGGML_CUDA=ON\""

# Full functionality mode
FULL_BASE_IMAGE=$CUDA_BASE_IMAGE
FULL_EXTRAS="$DEFAULT_CUDA_EXTRAS,vllm,llama-cpp,llama_cpp_server"
FULL_ENV_VARS="CMAKE_ARGS=\"-DGGML_CUDA=ON\""

# Default value settings
BASE_IMAGE=$CUDA_BASE_IMAGE
IMAGE_NAME="eosphorosai/dbgpt"
IMAGE_NAME_ARGS=""
PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
LANGUAGE="en"
LOAD_EXAMPLES="true"
BUILD_NETWORK=""
DB_GPT_INSTALL_MODE="default"
EXTRAS=""
ADDITIONAL_EXTRAS=""
DOCKERFILE="Dockerfile"
IMAGE_NAME_SUFFIX=""
USE_TSINGHUA_UBUNTU="true"
PYTHON_VERSION="3.11"  # Minimum supported Python version: 3.10
BUILD_ENV_VARS=""
ADDITIONAL_ENV_VARS=""

usage () {
    echo "USAGE: $0 [--base-image nvidia/cuda:12.1.0-devel-ubuntu22.04] [--image-name ${BASE_IMAGE}]"
    echo "  [-b|--base-image base image name] Base image name"
    echo "  [-n|--image-name image name] Current image name, default: ${IMAGE_NAME}"
    echo "  [--image-name-suffix image name suffix] Image name suffix"
    echo "  [-i|--pip-index-url pip index url] Pip index url, default: ${PIP_INDEX_URL}"
    echo "  [--language en or zh] You language, default: en"
    echo "  [--load-examples true or false] Whether to load examples to default database default: true"
    echo "  [--network network name] The network of docker build"
    echo "  [--install-mode mode name] Installation mode name, default: default"
    echo "                Available modes: default, openai, vllm, llama-cpp, full"
    echo "  [--extras extra packages] Comma-separated list of extra packages to install, overrides the default for the install mode"
    echo "  [--add-extras additional packages] Comma-separated list of additional extra packages to append to the default extras"
    echo "  [--env-vars \"ENV_VAR1=value1 ENV_VAR2=value2\"] Environment variables for build, overrides the default for the install mode"
    echo "  [--add-env-vars \"ENV_VAR1=value1 ENV_VAR2=value2\"] Additional environment variables to append to the default env vars"
    echo "  [--use-tsinghua-ubuntu true or false] Whether to use Tsinghua Ubuntu mirror, default: true"
    echo "  [--python-version version] Python version to use, default: ${PYTHON_VERSION}"
    echo "  [-f|--dockerfile dockerfile] Dockerfile name, default: ${DOCKERFILE}"
    echo "  [--list-modes] List all available install modes with their configurations"
    echo "  [-h|--help] Usage message"
}

list_modes() {
    echo "Available installation modes:"
    echo "--------------------------"
    
    # Default mode
    echo "Mode: default"
    echo "  Base image: $DEFAULT_BASE_IMAGE"
    echo "  Extras: $DEFAULT_EXTRAS"
    if [ -n "$DEFAULT_ENV_VARS" ]; then
        echo "  Environment Variables: $DEFAULT_ENV_VARS"
    fi
    echo "--------------------------"
    
    # OpenAI mode
    echo "Mode: openai"
    echo "  Base image: $OPENAI_BASE_IMAGE"
    echo "  Extras: $OPENAI_EXTRAS"
    if [ -n "$OPENAI_ENV_VARS" ]; then
        echo "  Environment Variables: $OPENAI_ENV_VARS"
    fi
    echo "--------------------------"
    
    # VLLM mode
    echo "Mode: vllm"
    echo "  Base image: $VLLM_BASE_IMAGE"
    echo "  Extras: $VLLM_EXTRAS"
    if [ -n "$VLLM_ENV_VARS" ]; then
        echo "  Environment Variables: $VLLM_ENV_VARS"
    fi
    echo "--------------------------"
    
    # LLAMA-CPP mode
    echo "Mode: llama-cpp"
    echo "  Base image: $LLAMA_CPP_BASE_IMAGE"
    echo "  Extras: $LLAMA_CPP_EXTRAS"
    if [ -n "$LLAMA_CPP_ENV_VARS" ]; then
        echo "  Environment Variables: $LLAMA_CPP_ENV_VARS"
    fi
    echo "--------------------------"
    
    # Full mode
    echo "Mode: full"
    echo "  Base image: $FULL_BASE_IMAGE"
    echo "  Extras: $FULL_EXTRAS"
    if [ -n "$FULL_ENV_VARS" ]; then
        echo "  Environment Variables: $FULL_ENV_VARS"
    fi
    echo "--------------------------"
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
        --image-name-suffix)
        IMAGE_NAME_SUFFIX="$2"
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
        --install-mode)
        DB_GPT_INSTALL_MODE="$2"
        shift # past argument
        shift # past value
        ;;
        --extras)
        EXTRAS="$2"
        shift # past argument
        shift # past value
        ;;
        --add-extras)
        ADDITIONAL_EXTRAS="$2"
        shift # past argument
        shift # past value
        ;;
        --env-vars)
        BUILD_ENV_VARS="$2"
        shift # past argument
        shift # past value
        ;;
        --add-env-vars)
        ADDITIONAL_ENV_VARS="$2"
        shift # past argument
        shift # past value
        ;;
        --use-tsinghua-ubuntu)
        USE_TSINGHUA_UBUNTU="$2"
        shift # past argument
        shift # past value
        ;;
        --python-version)
        PYTHON_VERSION="$2"
        shift # past argument
        shift # past value
        ;;
        -f|--dockerfile)
        DOCKERFILE="$2"
        shift # past argument
        shift # past value
        ;;
        --list-modes)
        list_modes
        exit 0
        ;;
        -h|--help)
        usage
        exit 0
        ;;
        *)
        usage
        exit 1
        ;;
    esac
done

# Configure based on the installation mode
if [ -n "$DB_GPT_INSTALL_MODE" ]; then
    # Check if it is a valid installation mode and set the corresponding variables
    case "$DB_GPT_INSTALL_MODE" in
        default)
            # If the user has not explicitly specified BASE_IMAGE, use the default value for this mode
            if [ "$BASE_IMAGE" == "$CUDA_BASE_IMAGE" ]; then
                BASE_IMAGE="$DEFAULT_BASE_IMAGE"
            fi
            # If the user has not explicitly specified EXTRAS, use the default value for this mode
            if [ -z "$EXTRAS" ]; then
                EXTRAS="$DEFAULT_EXTRAS"
            fi
            # If the user has not explicitly specified BUILD_ENV_VARS, use the default value for this mode
            if [ -z "$BUILD_ENV_VARS" ]; then
                BUILD_ENV_VARS="$DEFAULT_ENV_VARS"
            fi
            ;;
        openai)
            if [ "$BASE_IMAGE" == "$CUDA_BASE_IMAGE" ]; then
                BASE_IMAGE="$OPENAI_BASE_IMAGE"
            fi
            if [ -z "$EXTRAS" ]; then
                EXTRAS="$OPENAI_EXTRAS"
            fi
            if [ -z "$BUILD_ENV_VARS" ]; then
                BUILD_ENV_VARS="$OPENAI_ENV_VARS"
            fi
            ;;
        vllm)
            if [ "$BASE_IMAGE" == "$CUDA_BASE_IMAGE" ]; then
                BASE_IMAGE="$VLLM_BASE_IMAGE"
            fi
            if [ -z "$EXTRAS" ]; then
                EXTRAS="$VLLM_EXTRAS"
            fi
            if [ -z "$BUILD_ENV_VARS" ]; then
                BUILD_ENV_VARS="$VLLM_ENV_VARS"
            fi
            ;;
        llama-cpp)
            if [ "$BASE_IMAGE" == "$CUDA_BASE_IMAGE" ]; then
                BASE_IMAGE="$LLAMA_CPP_BASE_IMAGE"
            fi
            if [ -z "$EXTRAS" ]; then
                EXTRAS="$LLAMA_CPP_EXTRAS"
            fi
            if [ -z "$BUILD_ENV_VARS" ]; then
                BUILD_ENV_VARS="$LLAMA_CPP_ENV_VARS"
            fi
            ;;
        full)
            if [ "$BASE_IMAGE" == "$CUDA_BASE_IMAGE" ]; then
                BASE_IMAGE="$FULL_BASE_IMAGE"
            fi
            if [ -z "$EXTRAS" ]; then
                EXTRAS="$FULL_EXTRAS"
            fi
            if [ -z "$BUILD_ENV_VARS" ]; then
                BUILD_ENV_VARS="$FULL_ENV_VARS"
            fi
            ;;
        *)
            echo "Warning: Unknown install mode '$DB_GPT_INSTALL_MODE'. Using defaults."
            ;;
    esac

    # Set image name suffix to the installation mode
    if [ "$DB_GPT_INSTALL_MODE" != "default" ]; then
        IMAGE_NAME="$IMAGE_NAME-$DB_GPT_INSTALL_MODE"
    fi
fi

# If additional extras are specified, add them to the existing extras
if [ -n "$ADDITIONAL_EXTRAS" ]; then
    if [ -z "$EXTRAS" ]; then
        EXTRAS="$ADDITIONAL_EXTRAS"
    else
        EXTRAS="$EXTRAS,$ADDITIONAL_EXTRAS"
    fi
fi

# If additional environment variables are specified, add them to the existing environment variables
if [ -n "$ADDITIONAL_ENV_VARS" ]; then
    if [ -z "$BUILD_ENV_VARS" ]; then
        BUILD_ENV_VARS="$ADDITIONAL_ENV_VARS"
    else
        BUILD_ENV_VARS="$BUILD_ENV_VARS $ADDITIONAL_ENV_VARS"
    fi
fi

# If an image name argument is provided, use it as the image name
if [ -n "$IMAGE_NAME_ARGS" ]; then
    IMAGE_NAME=$IMAGE_NAME_ARGS
fi

# Add additional image name suffix
if [ -n "$IMAGE_NAME_SUFFIX" ]; then
    IMAGE_NAME="$IMAGE_NAME-$IMAGE_NAME_SUFFIX"
fi

echo "Begin build docker image"
echo "Base image: ${BASE_IMAGE}"
echo "Target image name: ${IMAGE_NAME}"
echo "Install mode: ${DB_GPT_INSTALL_MODE}"
echo "Extras: ${EXTRAS}"
if [ -n "$ADDITIONAL_EXTRAS" ]; then
    echo "Additional Extras: ${ADDITIONAL_EXTRAS}"
fi
if [ -n "$BUILD_ENV_VARS" ]; then
    echo "Environment Variables: ${BUILD_ENV_VARS}"
fi
echo "Python version: ${PYTHON_VERSION}"
echo "Use Tsinghua Ubuntu mirror: ${USE_TSINGHUA_UBUNTU}"

# Build environment variable arguments string
BUILD_ENV_ARGS=""
if [ -n "$BUILD_ENV_VARS" ]; then
    # Split the environment variables and add them as build arguments
    for env_var in $BUILD_ENV_VARS; do
        BUILD_ENV_ARGS="$BUILD_ENV_ARGS --build-arg $env_var"
    done
fi

docker build $BUILD_NETWORK \
    --build-arg USE_TSINGHUA_UBUNTU=$USE_TSINGHUA_UBUNTU \
    --build-arg BASE_IMAGE=$BASE_IMAGE \
    --build-arg PIP_INDEX_URL=$PIP_INDEX_URL \
    --build-arg LANGUAGE=$LANGUAGE \
    --build-arg LOAD_EXAMPLES=$LOAD_EXAMPLES \
    --build-arg EXTRAS=$EXTRAS \
    --build-arg PYTHON_VERSION=$PYTHON_VERSION \
    $BUILD_ENV_ARGS \
    -f $DOCKERFILE \
    -t $IMAGE_NAME $WORK_DIR/../../