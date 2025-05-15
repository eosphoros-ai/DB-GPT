# Proxy LLMs

DB-GPT can be deployed on servers with lower hardware requirements through proxy LLMs. DB-GPT supports many proxy LLMs, such as OpenAI, Azure, DeepSeek, Ollama, and more.

## Installation and Configuration

Installing DB-GPT with proxy LLM support requires using the `uv` package manager for a faster and more stable dependency management experience.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'OpenAI', value: 'openai'},
    {label: 'Azure', value: 'azure'},
    {label: 'DeepSeek', value: 'deepseek'},
    {label: 'Ollama', value: 'ollama'},
    {label: 'Qwen', value: 'qwen'},
    {label: 'ChatGLM', value: 'chatglm'},
    {label: 'WenXin', value: 'erniebot'},
  ]}>
  <TabItem value="openai" label="OpenAI">

### Install Dependencies

```bash
# Use uv to install dependencies needed for OpenAI proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure OpenAI

Edit the `configs/dbgpt-proxy-openai.toml` configuration file to specify your OpenAI API key:

```toml
# Model Configurations
[models]
[[models.llms]]
name = "gpt-3.5-turbo"
provider = "proxy/openai"
api_key = "your-openai-api-key"
# Optional: To use GPT-4, change the name to "gpt-4" or "gpt-4-turbo"

[[models.embeddings]]
name = "text-embedding-ada-002"
provider = "proxy/openai"
api_key = "your-openai-api-key"
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

  </TabItem>
  <TabItem value="azure" label="Azure">

### Install Dependencies

```bash
# Use uv to install dependencies needed for Azure OpenAI proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure Azure OpenAI

Edit the `configs/dbgpt-proxy-azure.toml` configuration file to specify your Azure OpenAI settings:

```toml
# Model Configurations
[models]
[[models.llms]]
name = "gpt-35-turbo"  # or your deployment model name
provider = "proxy/openai"
api_base = "https://your-resource-name.openai.azure.com/"
api_key = "your-azure-openai-api-key"
api_version = "2023-05-15"  # or your specific API version
api_type = "azure"
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-azure.toml
```

  </TabItem>
  <TabItem value="deepseek" label="DeepSeek">

### Install Dependencies

```bash
# Use uv to install dependencies needed for DeepSeek proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure DeepSeek

Edit the `configs/dbgpt-proxy-deepseek.toml` configuration file to specify your DeepSeek API key:

```toml
# Model Configurations
[models]
[[models.llms]]
# name = "deepseek-chat"
name = "deepseek-reasoner"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```

  </TabItem>
  <TabItem value="ollama" label="Ollama">

### Install Dependencies

```bash
# Use uv to install dependencies needed for Ollama proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_ollama" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure Ollama

Edit the `configs/dbgpt-proxy-ollama.toml` configuration file to specify your Ollama API base:

```toml
# Model Configurations
[models]
[[models.llms]]
name = "llama3"  # or any other model available in your Ollama instance
provider = "proxy/ollama"
api_base = "http://localhost:11434" # your-ollama-api-base

[[models.embeddings]]
name = "nomic-embed-text"  # or any other embedding model in Ollama
provider = "proxy/ollama"
api_base = "http://localhost:11434" # your-ollama-api-base
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-ollama.toml
```

  </TabItem>
  <TabItem value="qwen" label="Qwen (Tongyi)">

### Install Dependencies

```bash
# Use uv to install dependencies needed for Aliyun Qwen (Tongyi) proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_tongyi" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure Qwen

Create or edit a configuration file (e.g., `configs/dbgpt-proxy-tongyi.toml`):

```toml
# Model Configurations
[models]
[[models.llms]]
name = "qwen-turbo"  # or qwen-max, qwen-plus
provider = "proxy/tongyi"
api_key = "your-tongyi-api-key"
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-tongyi.toml
```

  </TabItem>
  <TabItem value="chatglm" label="ChatGLM (Zhipu)">

### Install Dependencies

```bash
# Use uv to install dependencies needed for Zhipu (ChatGLM) proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_zhipu" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure ChatGLM

Create or edit a configuration file (e.g., `configs/dbgpt-proxy-zhipu.toml`):

```toml
# Model Configurations
[models]
[[models.llms]]
name = "glm-4"  # or other available model versions
provider = "proxy/zhipu"
api_key = "your-zhipu-api-key"
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-zhipu.toml
```

  </TabItem>
  <TabItem value="erniebot" label="WenXin (Ernie)">

### Install Dependencies

```bash
# Use uv to install dependencies needed for Baidu WenXin proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure WenXin

Create or edit a configuration file (e.g., `configs/dbgpt-proxy-wenxin.toml`):

```toml
# Model Configurations
[models]
[[models.llms]]
name = "ERNIE-Bot-4.0"  # or ernie-bot, ernie-bot-turbo
provider = "proxy/wenxin"
api_key = "your-wenxin-api-key"
api_secret = "your-wenxin-api-secret"
```

### Run Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-wenxin.toml
```

  </TabItem>
</Tabs>

:::info note
If you are in the China region, you can add `--index-url=https://pypi.tuna.tsinghua.edu.cn/simple` at the end of the `uv sync` command for faster package downloads.
:::

## Visit Website

After starting the webserver, open your browser and visit [`http://localhost:5670`](http://localhost:5670)