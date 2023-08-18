#!/bin/bash

# Get cuda version by torch
CUDA_VERSION=`python -c "import torch;print(torch.version.cuda.replace('.', '') if torch.cuda.is_available() else '')"`

DEVICE="cpu"
CPU_OPT="basic"

if [ "${CUDA_VERSION}" = "" ]; then
    echo "CUDA not support, use cpu version"
else
    DEVICE="cu${CUDA_VERSION//./}"
    echo "CUDA version: $CUDA_VERSION, download path: $DEVICE"
fi

echo "Checking CPU support:"
CPU_SUPPORT=$(lscpu)

echo "$CPU_SUPPORT" | grep -q "avx "
if [ $? -eq 0 ]; then
    echo "CPU supports AVX."
    # CPU_OPT="AVX"
    # TODO AVX will failed on my cpu
else
  echo "CPU does not support AVX."
fi

echo "$CPU_SUPPORT" | grep -q "avx2"
if [ $? -eq 0 ]; then
  echo "CPU supports AVX2."
  CPU_OPT="AVX2"
else
  echo "CPU does not support AVX2."
fi

echo "$CPU_SUPPORT" | grep -q "avx512"
if [ $? -eq 0 ]; then
  echo "CPU supports AVX512."
  CPU_OPT="AVX512"
else
  echo "CPU does not support AVX512."
fi

EXTRA_INDEX_URL="https://jllllll.github.io/llama-cpp-python-cuBLAS-wheels/$CPU_OPT/$DEVICE"

echo "install llama-cpp-python from --extra-index-url ${EXTRA_INDEX_URL}"
python -m pip install llama-cpp-python --force-reinstall --no-cache --prefer-binary --extra-index-url=$EXTRA_INDEX_URL
