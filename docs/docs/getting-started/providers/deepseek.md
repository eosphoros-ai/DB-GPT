---
sidebar_position: 2
title: DeepSeek
---

# DeepSeek

Configure DB-GPT to use DeepSeek's language models for chat and reasoning.

## Prerequisites

- A [DeepSeek API key](https://platform.deepseek.com/)
- DB-GPT installed with `proxy_openai` extra

## Install dependencies

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts"
```

:::info Embedding model
DeepSeek does not provide embedding models. The default config uses a HuggingFace embedding model (`BAAI/bge-large-zh-v1.5`). If using this, also add:

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
  --extra "dbgpts" \
  --extra "hf" \
  --extra "cpu"
```
:::

## Configuration

Edit `configs/dbgpt-proxy-deepseek.toml`:

```toml
[models]
[[models.llms]]
name = "deepseek-v4-pro"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"
# Disable V4-Pro thinking mode for strict ReAct output parsing.
thinking_enabled = false

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# Uncomment to use a local model path:
# path = "models/bge-large-zh-v1.5"
```

## Available models

| Model | Config name | Notes |
|---|---|---|
| DeepSeek-V4-Pro | `deepseek-v4-pro` | 1M context, advanced reasoning, coding, and agent tasks |
| DeepSeek-R1 | `deepseek-reasoner` | Strong reasoning, chain-of-thought |
| DeepSeek-V3 | `deepseek-chat` | General purpose chat |

For ReAct agents, keep `thinking_enabled = false` with `deepseek-v4-pro`. DeepSeek
V4-Pro enables thinking mode by default, which can add reasoning blocks before the
strict `Thought/Action/Action Input` response format.

## Start the server

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```

## Troubleshooting

| Issue | Solution |
|---|---|
| `AuthenticationError` | Verify your DeepSeek API key at [platform.deepseek.com](https://platform.deepseek.com/) |
| Embedding download slow | Pre-download the model or use a mirror (`UV_INDEX_URL`) |
| Out of memory for embedding | Use `--extra "cpu"` to run embeddings on CPU |

## What's next

- [Getting Started](/docs/getting-started/quick-start) — Full setup walkthrough
- [Model Providers](/docs/getting-started/providers/) — Try other providers
