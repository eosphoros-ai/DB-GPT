---
sidebar_position: 1
title: Prerequisites
summary: "What you need before running DB-GPT locally or with Docker"
read_when:
  - You want to confirm Python, uv, Docker, or GPU requirements before setup
  - You are deciding between API-proxy mode and local-model mode
---

# Prerequisites

Everything you need before installing DB-GPT.

:::tip Quick check
Already have Python 3.10+ and uv? Skip to [Getting Started](/docs/getting-started/quick-start).
:::

## Required

| Requirement | Version | Check command |
|---|---|---|
| **Python** | 3.10 or newer | `python --version` |
| **uv** | Latest | `uv --version` |
| **Git** | Any recent | `git --version` |

### Python

DB-GPT requires **Python 3.10+**. We recommend Python 3.11 for the best compatibility.

```bash
python --version
# Python 3.11.x
```

:::info
If you need to manage multiple Python versions, consider using [pyenv](https://github.com/pyenv/pyenv) or [conda](https://docs.conda.io/).
:::

### uv (package manager)

Starting from v0.7.0, DB-GPT uses [uv](https://docs.astral.sh/uv/) for environment and package management, providing faster and more stable dependency resolution.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
  <TabItem value="shell" label="macOS / Linux" default>

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

  </TabItem>
  <TabItem value="pipx" label="pipx">

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade pipx
python -m pipx ensurepath
pipx install uv --global
```

  </TabItem>
  <TabItem value="other" label="Other">

See the full [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) for Homebrew, Scoop, and other methods.

  </TabItem>
</Tabs>

Verify the installation:

```bash
uv --version
```

## Choose the right setup first

- **Fastest setup:** API proxy model (OpenAI, DeepSeek, Qwen, SiliconFlow) — no GPU required
- **Privacy-first local setup:** Ollama — local model runtime, optional GPU
- **High-performance local inference:** vLLM or HuggingFace GPU stack — NVIDIA GPU required

## Optional (based on deployment)

### For Web UI development

| Requirement | Version | Check command |
|---|---|---|
| **Node.js** | 20.19 or newer (frontend development) | `node --version` |
| **Yarn Classic** | 1.22.22; run `corepack enable` first | `yarn --version` |

### For local model deployment

| Requirement | Details |
|---|---|
| **NVIDIA GPU** | CUDA 12.1+ for GPU-accelerated inference |
| **CUDA Toolkit** | Required for vLLM, HuggingFace Transformers with GPU |
| **Sufficient VRAM** | 8 GB+ for 7B models, 24 GB+ for 13B+ models |

:::info
If you only use API proxy models (OpenAI, DeepSeek, etc.), **no GPU is required**. You can run on a CPU-only machine.
:::

### For Docker deployment

| Requirement | Version | Check command |
|---|---|---|
| **Docker** | 20.10+ | `docker --version` |
| **Docker Compose** | 2.0+ | `docker compose version` |
| **NVIDIA Container Toolkit** | Latest (GPU only) | `nvidia-smi` |

## System resources

| Deployment Type | CPU | RAM | Disk |
|---|---|---|---|
| **API proxy only** | 2 cores | 4 GB | 10 GB |
| **Local 7B model** | 4 cores | 16 GB | 30 GB |
| **Local 13B+ model** | 8 cores | 32 GB | 60 GB |

## Network considerations (China)

If you are in the China region, configure a PyPI mirror for faster package downloads:

```bash
# Set the mirror as environment variable
echo "export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.bashrc
source ~/.bashrc
```

Or append `--index-url` to each `uv sync` command:

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --index-url=https://pypi.tuna.tsinghua.edu.cn/simple
```

## Next step

Ready to go? Head to [Getting Started](/docs/getting-started/quick-start) for a 5-minute setup.
