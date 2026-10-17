---
sidebar_position: 1
title: 前置条件
summary: "在本地或通过 Docker 运行 DB-GPT 前需要准备的环境"
read_when:
  - 你想在安装前确认 Python、uv、Docker 或 GPU 相关要求
  - 你正在 API 代理模式和本地模型模式之间做选择
---

# 前置条件

这里列出了安装 DB-GPT 之前需要准备的全部内容。

:::tip 快速检查
如果你已经安装了 Python 3.10+ 和 uv，可以直接跳到 [快速开始](/docs/getting-started/quick-start)。
:::

## 必需环境

| 依赖项 | 版本 | 检查命令 |
|---|---|---|
| **Python** | 3.10 或更高 | `python --version` |
| **uv** | 最新版 | `uv --version` |
| **Git** | 任意较新版本 | `git --version` |

### Python

DB-GPT 需要 **Python 3.10+**。推荐使用 Python 3.11 以获得更好的兼容性。

```bash
python --version
# Python 3.11.x
```

:::info
如果你需要管理多个 Python 版本，可以考虑使用 [pyenv](https://github.com/pyenv/pyenv) 或 [conda](https://docs.conda.io/)。
:::

### uv（包管理器）

从 v0.7.0 开始，DB-GPT 使用 [uv](https://docs.astral.sh/uv/) 进行环境与依赖管理，依赖解析更快也更稳定。

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

如果你使用 Homebrew、Scoop 等其他方式，请查看完整的 [uv 安装指南](https://docs.astral.sh/uv/getting-started/installation/)。

  </TabItem>
</Tabs>

安装完成后验证：

```bash
uv --version
```

## 先选择合适的部署方式

- **最快上手**：API 代理模型（OpenAI、DeepSeek、Qwen、SiliconFlow）—— 不需要 GPU
- **注重隐私的本地部署**：Ollama —— 本地模型运行时，可选 GPU
- **高性能本地推理**：vLLM 或 HuggingFace GPU 方案 —— 需要 NVIDIA GPU

## 可选环境（按部署方式决定）

### 用于 Web UI 开发

| 依赖项 | 版本 | 检查命令 |
|---|---|---|
| **Node.js** | 20.19 或更高（前端开发） | `node --version` |
| **Yarn Classic** | 1.22.22；先运行 `corepack enable` | `yarn --version` |

### 用于本地模型部署

| 依赖项 | 说明 |
|---|---|
| **NVIDIA GPU** | GPU 推理推荐 CUDA 12.1+ |
| **CUDA Toolkit** | 使用 vLLM 或 HuggingFace GPU 推理时需要 |
| **足够的显存** | 7B 模型建议 8 GB+，13B+ 模型建议 24 GB+ |

:::info
如果你只使用 API 代理模型（OpenAI、DeepSeek 等），**不需要 GPU**，CPU 机器即可运行。
:::

### 用于 Docker 部署

| 依赖项 | 版本 | 检查命令 |
|---|---|---|
| **Docker** | 20.10+ | `docker --version` |
| **Docker Compose** | 2.0+ | `docker compose version` |
| **NVIDIA Container Toolkit** | 最新版（仅 GPU 场景） | `nvidia-smi` |

## 系统资源建议

| 部署类型 | CPU | 内存 | 磁盘 |
|---|---|---|---|
| **仅 API 代理** | 2 核 | 4 GB | 10 GB |
| **本地 7B 模型** | 4 核 | 16 GB | 30 GB |
| **本地 13B+ 模型** | 8 核 | 32 GB | 60 GB |

## 网络注意事项（中国区）

如果你在中国大陆，建议配置 PyPI 镜像以加快依赖下载：

```bash
# 将镜像地址设置为环境变量
echo "export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.bashrc
source ~/.bashrc
```

或者在 `uv sync` 命令中附加 `--index-url`：

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --index-url=https://pypi.tuna.tsinghua.edu.cn/simple
```

## 下一步

准备好了？前往 [快速开始](/docs/getting-started/quick-start) 按 5 分钟流程完成安装。
