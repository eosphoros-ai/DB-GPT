---
sidebar_position: 2
title: Getting Started
summary: "Shortest path from clone to a working DB-GPT chat"
read_when:
  - You want the first successful DB-GPT run with the least setup
  - You need a concrete first-run checklist and quick verification
---

# Getting Started

Goal: go from zero to a first working chat with minimal setup.

:::info Fastest path
Use an **API proxy** (OpenAI or DeepSeek) — no GPU required. You will have a working DB-GPT chat in under 5 minutes.
:::

## What you need

* Python 3.10 or newer
* uv package manager

:::tip
Check your versions with `python --version` and `uv --version`. Full requirements: [Prerequisites](/docs/getting-started/prerequisites).
:::

## Quick setup

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### Step 1 — Clone the repository

```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
cd DB-GPT
```

### Step 2 — Install dependencies

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

### Step 3 — Configure your model

<Tabs>
  <TabItem value="openai" label="OpenAI" default>

Edit `configs/dbgpt-proxy-openai.toml` and set your API key:

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

Edit `configs/dbgpt-proxy-deepseek.toml` and set your API key:

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
The default embedding model is `BAAI/bge-large-zh-v1.5`. If using a HuggingFace embedding, also add `--extra "hf"` and `--extra "cpu"` to the install command.
:::

  </TabItem>
  <TabItem value="ollama" label="Ollama">

Make sure [Ollama](https://ollama.ai) is running, then edit `configs/dbgpt-proxy-ollama.toml`:

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

### Step 4 — Start the server

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

### Step 5 — Open the Web UI

Open your browser and visit **[http://localhost:5670](http://localhost:5670)**.

:::tip Verify it works
If the Web UI loads and you can start a chat conversation, your DB-GPT is ready for use.
:::

## Verify

- The webserver is running
- Your model config loads without errors
- The Web UI opens at `http://localhost:5670`
- SQLite is available as the default metadata store

## Common first-run issues

- **`uv: command not found`**
  - Install uv first: [Prerequisites](/docs/getting-started/prerequisites)
- **Model key/auth errors**
  - Re-check the provider config under `configs/`
  - Start here: [Model Providers](/docs/getting-started/providers/)
- **Web UI does not load**
  - Confirm the server is listening on port `5670`
  - Check the server logs in the terminal where you started DB-GPT
- **Local model does not respond**
  - Confirm Ollama or your local inference backend is already running

## If you need more

- **Run the web front-end separately**

  ```bash
  cd web && npm install
  cp .env.template .env
  # Edit .env — set API_BASE_URL=http://localhost:5670
  npm run dev
  ```

  Then open [http://localhost:3000](http://localhost:3000).

- **Use the install helper**

  ```bash
  uv run install_help.py install-cmd --interactive
  uv run install_help.py list
  ```

- **Use a different database**
  - Default is SQLite
  - For MySQL, PostgreSQL, and others, see [Data Sources](/docs/getting-started/concepts/data-sources)

- **Useful environment variables**
  - `UV_INDEX_URL` — PyPI mirror URL
  - `OPENAI_API_KEY` — alternative to storing the key in TOML
  - `CUDA_VISIBLE_DEVICES` — GPU device selection
  - Full reference: [Config Reference](/docs/config/config-reference)

## Go deeper

| Topic | Link |
|---|---|
| Full architecture overview | [Architecture](/docs/getting-started/concepts/architecture) |
| Connect more model providers | [Model Providers](/docs/getting-started/providers/) |
| Docker deployment | [Docker](/docs/getting-started/deploy/docker) |
| Knowledge base setup | [Knowledge Base](/docs/getting-started/web-ui/knowledge-base) |

## Next steps

* Configure model providers: [Model Providers](/docs/getting-started/providers/)
* Deploy with Docker: [Docker Deployment](/docs/getting-started/deploy/docker)
* Explore the Web UI: [Web UI Guide](/docs/getting-started/web-ui/)
* Build your first AWEL workflow: [AWEL Quickstart](/docs/awel/cookbook/quickstart_basic_awel_workflow)
