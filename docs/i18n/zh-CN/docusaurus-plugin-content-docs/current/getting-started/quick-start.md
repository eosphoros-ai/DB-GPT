---
sidebar_position: 2
title: 快速开始
summary: "从 clone 仓库到跑通 DB-GPT 对话的最短路径"
read_when:
  - 你希望用最少步骤完成第一次成功启动
  - 你需要一份明确的首跑清单和快速验证方式
---

# 快速开始

目标：用最少配置从零开始跑通第一次可用对话。

:::info 最快路径
使用 **API 代理模式**（OpenAI 或 DeepSeek）—— 不需要 GPU。一般 5 分钟内就可以跑通一个可用的 DB-GPT 对话。
:::

## 你需要准备什么

* Python 3.10 或更高版本
* uv 包管理器

:::tip
先用 `python --version` 和 `uv --version` 检查版本。完整要求见：[前置条件](/docs/getting-started/prerequisites)。
:::

## 快速配置

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### 第 1 步 —— 克隆仓库

```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
cd DB-GPT
```

### 第 2 步 —— 安装依赖

<Tabs>
  <TabItem value="openai" label="OpenAI (proxy)" default>

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts"
```

  </TabItem>
  <TabItem value="deepseek" label="DeepSeek (proxy)">

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts"
```

  </TabItem>
  <TabItem value="ollama" label="Ollama (local)">

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_ollama" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts"
```

  </TabItem>
</Tabs>

### 第 3 步 —— 配置模型

<Tabs>
  <TabItem value="openai" label="OpenAI" default>

编辑 `configs/dbgpt-proxy-openai.toml`，填入你的 API Key：

```toml
[models]
[[models.llms]]
name = "chatgpt_proxyllm"
provider = "proxy/openai"
api_key = "your-openai-api-key"    # <-- replace this

[[models.embeddings]]
name = "text-embedding-3-small"
provider = "proxy/openai"
api_key = "your-openai-api-key"    # <-- replace this
```

  </TabItem>
  <TabItem value="deepseek" label="DeepSeek">

编辑 `configs/dbgpt-proxy-deepseek.toml`，填入你的 API Key：

```toml
[models]
[[models.llms]]
name = "deepseek-reasoner"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"  # <-- replace this

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
```

:::info
默认 embedding 模型为 `BAAI/bge-large-zh-v1.5`。如果你使用 HuggingFace embedding，还需要在安装命令中增加 `--extra "hf"` 和 `--extra "cpu"`。
:::

  </TabItem>
  <TabItem value="ollama" label="Ollama">

确认 [Ollama](https://ollama.ai) 已经启动，然后编辑 `configs/dbgpt-proxy-ollama.toml`：

```toml
[models]
[[models.llms]]
name = "qwen2.5:latest"
provider = "proxy/ollama"
api_base = "http://localhost:11434"

[[models.embeddings]]
name = "nomic-embed-text:latest"
provider = "proxy/ollama"
api_base = "http://localhost:11434"
```

  </TabItem>
</Tabs>

### 第 4 步 —— 启动服务

<Tabs>
  <TabItem value="openai" label="OpenAI" default>

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

  </TabItem>
  <TabItem value="deepseek" label="DeepSeek">

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```

  </TabItem>
  <TabItem value="ollama" label="Ollama">

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-ollama.toml
```

  </TabItem>
</Tabs>

### 第 5 步 —— 打开 Web UI

打开浏览器访问 **[http://localhost:5670](http://localhost:5670)**。

:::tip 验证是否成功
如果 Web UI 能打开，并且你可以发起聊天对话，就说明 DB-GPT 已经可以使用了。
:::

## 验证清单

- webserver 已经启动
- 模型配置加载没有报错
- Web UI 可以在 `http://localhost:5670` 打开
- SQLite 作为默认元数据存储可正常使用

## 首次启动常见问题

- **`uv: command not found`**
  - 先安装 uv：[前置条件](/docs/getting-started/prerequisites)
- **模型 Key / 认证错误**
  - 重新检查 `configs/` 下的提供方配置
  - 从这里开始排查：[模型提供方](/docs/getting-started/providers/)
- **Web UI 无法打开**
  - 确认服务在 `5670` 端口监听
  - 查看启动 DB-GPT 的终端日志
- **本地模型没有响应**
  - 确认 Ollama 或本地推理后端已经运行

## 如果你还需要更多能力

- **单独运行前端**

  ```bash
  cd web && npm install
  cp .env.template .env
  # Edit .env — set API_BASE_URL=http://localhost:5670
  npm run dev
  ```

  然后打开 [http://localhost:3000](http://localhost:3000)。

- **使用安装辅助脚本**

  ```bash
  uv run install_help.py install-cmd --interactive
  uv run install_help.py list
  ```

- **使用其他数据库**
  - 默认使用 SQLite
  - 如果要使用 MySQL、PostgreSQL 等，请参考 [数据源](/docs/getting-started/concepts/data-sources)

- **常用环境变量**
  - `UV_INDEX_URL` —— PyPI 镜像地址
  - `OPENAI_API_KEY` —— 替代写入 TOML 的 API Key 方式
  - `CUDA_VISIBLE_DEVICES` —— GPU 设备选择
  - 完整说明见：[配置参考](/docs/config/config-reference)

## 继续深入

| 主题 | 链接 |
|---|---|
| 完整架构概览 | [架构](/docs/getting-started/concepts/architecture) |
| 接入更多模型提供方 | [模型提供方](/docs/getting-started/providers/) |
| Docker 部署 | [Docker](/docs/getting-started/deploy/docker) |
| 知识库配置 | [Knowledge Base](/docs/getting-started/web-ui/knowledge-base) |

## 下一步

* 配置模型提供方：[模型提供方](/docs/getting-started/providers/)
* 使用 Docker 部署：[Docker 部署](/docs/getting-started/deploy/docker)
* 了解 Web UI：[Web UI 指南](/docs/getting-started/web-ui/)
* 构建第一个 AWEL 工作流：[AWEL Quickstart](/docs/awel/cookbook/quickstart_basic_awel_workflow)
