---
id: docker-build-guide
title: DB-GPT Docker Build Guide
sidebar_label: Docker Build Guide
description: Comprehensive guide for building DB-GPT Docker images with various configurations
keywords:
  - DB-GPT
  - Docker
  - Build
  - CUDA
  - OpenAI
  - VLLM
  - Llama-cpp
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';

# DB-GPT Docker Build Guide

This guide provides comprehensive instructions for building DB-GPT Docker images with various configurations using the `docker/base/build_image.sh` script.

## Overview

The DB-GPT build script allows you to create Docker images tailored to your specific requirements. You can choose from predefined installation modes or customize the build with specific extras, environment variables, and other settings.

## Available Installation Modes

<Tabs>
  <TabItem value="default" label="Default" default>
    CUDA-based image with standard features.
    
    ```bash
    bash docker/base/build_image.sh
    ```
    
    Includes: CUDA support, proxy integrations (OpenAI, Ollama, Zhipuai, Anthropic, Qianfan, Tongyi), RAG capabilities, graph RAG, Hugging Face integration, and quantization support.
  </TabItem>
  <TabItem value="openai" label="OpenAI">
    CPU-based image optimized for OpenAI API usage.
    
    ```bash
    bash docker/base/build_image.sh --install-mode openai
    ```
    
    Includes: Basic functionality, all proxy integrations, and RAG capabilities without GPU acceleration.
  </TabItem>
  <TabItem value="vllm" label="VLLM">
    CUDA-based image with VLLM for optimized inference.
    
    ```bash
    bash docker/base/build_image.sh --install-mode vllm
    ```
    
    Includes: All default features plus VLLM support for high-performance inference.
  </TabItem>
  <TabItem value="llama-cpp" label="Llama-cpp">
    CUDA-based image with Llama-cpp support.
    
    ```bash
    bash docker/base/build_image.sh --install-mode llama-cpp
    ```
    
    Includes: All default features plus Llama-cpp and Llama-cpp server with CUDA acceleration enabled via `CMAKE_ARGS="-DGGML_CUDA=ON"`.
  </TabItem>
  <TabItem value="full" label="Full">
    CUDA-based image with all available features.
    
    ```bash
    bash docker/base/build_image.sh --install-mode full
    ```
    
    Includes: All features from other modes plus embedding capabilities.
  </TabItem>
</Tabs>

## Basic Usage

### View Available Modes

To see all available installation modes and their configurations:

```bash
bash docker/base/build_image.sh --list-modes
```

### Get Help

Display all available options:

```bash
bash docker/base/build_image.sh --help
```

## Customization Options

### Python Version

DB-GPT requires Python 3.10 or higher. The default is Python 3.11, but you can specify a different version:

```bash
bash docker/base/build_image.sh --python-version 3.10
```

### Custom Image Name

Set a custom name for the built image:

```bash
bash docker/base/build_image.sh --image-name mycompany/dbgpt
```

### Image Name Suffix

Add a suffix to the image name for versioning or environment identification:

```bash
bash docker/base/build_image.sh --image-name-suffix v1.0
```

This will generate `eosphorosai/dbgpt-v1.0` for the default mode or `eosphorosai/dbgpt-MODE-v1.0` for specific modes.

### PIP Mirror

Choose a different PIP index URL:

```bash
bash docker/base/build_image.sh --pip-index-url https://pypi.org/simple
```

### Ubuntu Mirror

Control whether to use Tsinghua Ubuntu mirror:

```bash
bash docker/base/build_image.sh --use-tsinghua-ubuntu false
```

### Language Preference

Set your preferred language (default is English):

```bash
bash docker/base/build_image.sh --language zh
```

## Advanced Customization

### Custom Extras

You can customize the Python package extras installed in the image:

<Tabs>
  <TabItem value="override" label="Override Extras" default>
    Completely replace the default extras with your own selection:
    
    ```bash
    bash docker/base/build_image.sh --extras "base,proxy_openai,rag,storage_chromadb"
    ```
  </TabItem>
  <TabItem value="add" label="Add Extras">
    Keep the default extras and add more:
    
    ```bash
    bash docker/base/build_image.sh --add-extras "storage_milvus,storage_elasticsearch,datasource_postgres"
    ```
  </TabItem>
  <TabItem value="mode-specific" label="Mode-Specific">
    Add specific extras to a particular installation mode:
    
    ```bash
    bash docker/base/build_image.sh --install-mode vllm --add-extras "storage_milvus,datasource_postgres"
    ```
  </TabItem>
</Tabs>

#### Available Extra Options

Here are some useful extras you can add:

| Extra Package | Description |
|--------------|-------------|
| `storage_milvus` | Vector store integration with Milvus |
| `storage_elasticsearch` | Vector store integration with Elasticsearch |
| `datasource_postgres` | Database connector for PostgreSQL |
| `vllm` | VLLM integration for optimized inference |
| `llama_cpp` | Llama-cpp Python bindings |
| `llama_cpp_server` | Llama-cpp HTTP server |

You can run `uv run install_help.py list` in your local DB-GPT repository to see all available extras.

### Environment Variables

DB-GPT build supports environment variables for specialized builds. The main environment variable used is `CMAKE_ARGS` which is particularly important for Llama-cpp compilation.

<Tabs>
  <TabItem value="override-env" label="Override Env Vars" default>
    Replace the default environment variables:
    
    ```bash
    bash docker/base/build_image.sh --env-vars "CMAKE_ARGS=\"-DGGML_CUDA=ON -DLLAMA_CUBLAS=ON\""
    ```
  </TabItem>
  <TabItem value="add-env" label="Add Env Vars">
    Add additional environment variables:
    
    ```bash
    bash docker/base/build_image.sh --install-mode llama-cpp --add-env-vars "FORCE_CMAKE=1"
    ```
  </TabItem>
</Tabs>

:::note
For Llama-cpp mode, `CMAKE_ARGS="-DGGML_CUDA=ON"` is automatically set to enable CUDA acceleration.
:::

### Docker Network

Specify a Docker network for building:

```bash
bash docker/base/build_image.sh --network host
```

### Custom Dockerfile

Use a custom Dockerfile:

```bash
bash docker/base/build_image.sh --dockerfile Dockerfile.custom
```

## Example Scenarios

### Enterprise DB-GPT with PostgreSQL and Elasticsearch

Build a full-featured enterprise version with PostgreSQL and Elasticsearch support:

```bash
bash docker/base/build_image.sh --install-mode full \
  --add-extras "storage_elasticsearch,datasource_postgres" \
  --image-name-suffix enterprise \
  --python-version 3.10 \
  --load-examples false
```

### Optimized Llama-cpp for Specific Hardware

Build with custom Llama-cpp optimization flags:

```bash
bash docker/base/build_image.sh --install-mode llama-cpp \
  --env-vars "CMAKE_ARGS=\"-DGGML_CUDA=ON -DGGML_AVX2=OFF -DGGML_AVX512=ON\"" \
  --python-version 3.11
```

### Lightweight OpenAI Proxy

Build a minimal OpenAI proxy image:

```bash
bash docker/base/build_image.sh --install-mode openai \
  --use-tsinghua-ubuntu false \
  --pip-index-url https://pypi.org/simple \
  --load-examples false
```

### Development Build with Milvus

Build a development version with Milvus support:

```bash
bash docker/base/build_image.sh --install-mode vllm \
  --add-extras "storage_milvus" \
  --image-name-suffix dev
```

## Troubleshooting

<details>
<summary>Common Build Issues</summary>

### CUDA Not Found

If you encounter CUDA-related errors:

```bash
# Try building with a different CUDA base image
bash docker/base/build_image.sh --base-image nvidia/cuda:12.1.0-devel-ubuntu22.04
```

### Package Installation Failures

If extras fail to install:

```bash
# Try building with fewer extras to isolate the problem
bash docker/base/build_image.sh --extras "base,proxy_openai,rag"
```

### Network Issues

If you encounter network problems:

```bash
# Use a specific network
bash docker/base/build_image.sh --network host
```

</details>

## API Reference

### Script Options

| Option | Description | Default Value |
|--------|-------------|---------------|
| `--install-mode` | Installation mode | `default` |
| `--base-image` | Base Docker image | `nvidia/cuda:12.4.0-devel-ubuntu22.04` |
| `--image-name` | Docker image name | `eosphorosai/dbgpt` |
| `--image-name-suffix` | Suffix for image name | ` ` |
| `--pip-index-url` | PIP mirror URL | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| `--language` | Interface language | `en` |
| `--load-examples` | Load example data | `true` |
| `--python-version` | Python version | `3.11` |
| `--use-tsinghua-ubuntu` | Use Tsinghua Ubuntu mirror | `true` |
| `--extras` | Extra packages to install | Mode dependent |
| `--add-extras` | Additional extra packages | ` ` |
| `--env-vars` | Build environment variables | Mode dependent |
| `--add-env-vars` | Additional environment variables | ` ` |
| `--dockerfile` | Dockerfile to use | `Dockerfile` |
| `--network` | Docker network to use | ` ` |

## Additional Resources

- [DB-GPT Documentation](https://github.com/eosphoros-ai/DB-GPT)
- [Docker Documentation](https://docs.docker.com/)
- [CUDA Documentation](https://docs.nvidia.com/cuda/)