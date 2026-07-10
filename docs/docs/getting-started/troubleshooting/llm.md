---
sidebar_position: 2
title: Model Issues
---

# Model Issues

Common problems with model configuration, loading, and generation.

## API key errors

**Symptom:** `401 Unauthorized`, `Invalid API key`, or `Authentication failed`.

**Fix:**

1. Verify your API key is correctly set in the TOML config:

```toml
[[models.llms]]
api_key = "sk-..."  # Must be a valid key
```

2. Or use environment variables:

```toml
[[models.llms]]
api_key = "${env:OPENAI_API_KEY}"
```

```bash
export OPENAI_API_KEY="sk-your-actual-key"
```

3. Check that the key has sufficient permissions and credits with the provider.

## Model not found

**Symptom:** `Model 'xxx' not found` or `No model registered`.

**Fix:**

1. Check the model name in your config matches the provider's expected format:

| Provider | Example Name |
|---|---|
| OpenAI | `chatgpt_proxyllm`, `gpt-4o` |
| DeepSeek | `deepseek-v4-pro`, `deepseek-chat`, `deepseek-reasoner` |
| Ollama | `qwen2.5:latest` (must be pulled first) |
| HuggingFace | `THUDM/glm-4-9b-chat-hf` |

2. For Ollama, ensure the model is downloaded:

```bash
ollama pull qwen2.5:latest
ollama list  # Verify it appears
```

3. For cluster deployments, verify workers are registered:

```bash
dbgpt model list
```

## Ollama connection refused

**Symptom:** `Connection refused` when using Ollama provider.

**Fix:**

1. Ensure Ollama is running:

```bash
ollama serve
# Or check: curl http://localhost:11434/api/tags
```

2. If running DB-GPT in Docker, use the host network address instead of `localhost`:

```toml
[[models.llms]]
api_base = "http://host.docker.internal:11434"  # Docker for Mac/Windows
# Or use the host's actual IP address
```

## Out of memory (OOM)

**Symptom:** `CUDA out of memory` or `RuntimeError: CUDA error`.

**Fix:**

1. Use a smaller model:

```toml
[[models.llms]]
name = "Qwen2.5-Coder-0.5B-Instruct"  # Smaller model
```

2. Enable quantization:

```bash
dbgpt start worker --model_name ... --load_4bit
```

3. Limit GPU memory:

```bash
CUDA_VISIBLE_DEVICES=0 uv run dbgpt start webserver ...
```

4. Or switch to an API proxy (no GPU needed):

```toml
[[models.llms]]
provider = "proxy/openai"  # Uses remote API instead of local GPU
```

## Slow model responses

**Symptom:** Very slow response times or timeouts.

**Possible causes and fixes:**

| Cause | Fix |
|---|---|
| Model downloading on first run | Wait for download to complete (check logs) |
| Insufficient GPU VRAM | Use quantization or a smaller model |
| Slow network to API | Check connectivity to provider endpoint |
| Large context window | Reduce `max_context_size` in config |

## Embedding model errors

**Symptom:** `Embedding model not found` or knowledge base operations fail.

**Fix:**

1. Ensure an embedding model is configured:

```toml
[[models.embeddings]]
name = "text-embedding-3-small"
provider = "proxy/openai"
api_key = "your-key"
```

2. For HuggingFace embeddings, ensure the model is downloaded or accessible:

```toml
[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# path = "/path/to/local/model"  # Optional: local path
```

3. Add the HuggingFace extra if using local embeddings:

```bash
uv sync --all-packages --extra "hf" --extra "cpu" ...
```

## Reranker not working

**Symptom:** RAG results not improving with reranker enabled.

**Fix:**

Ensure reranker is configured in your TOML:

```toml
[[models.rerankers]]
name = "BAAI/bge-reranker-base"
provider = "hf"
```

Or for SiliconFlow:

```toml
[[models.rerankers]]
name = "BAAI/bge-reranker-v2-m3"
provider = "proxy/siliconflow"
api_key = "${env:SILICONFLOW_API_KEY}"
```

## Still stuck?

- Check [LLM FAQ](/docs/faq/llm) for more solutions
- Review the [Model Providers](/docs/getting-started/providers/) documentation
- Search [GitHub Issues](https://github.com/eosphoros-ai/DB-GPT/issues)
