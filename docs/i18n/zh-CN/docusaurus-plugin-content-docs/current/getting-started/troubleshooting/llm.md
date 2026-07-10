---
sidebar_position: 2
title: 模型问题
---

# 模型问题

这里汇总了模型配置、加载和推理过程中常见的问题。

## API Key 错误

**现象：** `401 Unauthorized`、`Invalid API key` 或 `Authentication failed`。

**解决方法：**

1. 确认你的 API Key 已在 TOML 配置中正确设置：

```toml
[[models.llms]]
api_key = "sk-..."  # 必须为有效的 key
```

2. 或者使用环境变量：

```toml
[[models.llms]]
api_key = "${env:OPENAI_API_KEY}"
```

```bash
export OPENAI_API_KEY="sk-your-actual-key"
```

3. 确认该 Key 在服务提供方侧拥有足够权限，并且账户余额或额度正常。

## 找不到模型

**现象：** `Model 'xxx' not found` 或 `No model registered`。

**解决方法：**

1. 检查配置中的模型名称是否符合服务提供方要求的格式：

| Provider | 示例名称 |
|---|---|
| OpenAI | `chatgpt_proxyllm`, `gpt-4o` |
| DeepSeek | `deepseek-v4-pro`, `deepseek-chat`, `deepseek-reasoner` |
| Ollama | `qwen2.5:latest`（需先拉取） |
| HuggingFace | `THUDM/glm-4-9b-chat-hf` |

2. 对于 Ollama，请确认模型已经下载：

```bash
ollama pull qwen2.5:latest
ollama list  # 确认列表中已存在
```

3. 对于集群部署，确认 worker 已注册：

```bash
dbgpt model list
```

## Ollama 连接被拒绝

**现象：** 使用 Ollama provider 时出现 `Connection refused`。

**解决方法：**

1. 确认 Ollama 服务已启动：

```bash
ollama serve
# 或检查：curl http://localhost:11434/api/tags
```

2. 如果 DB-GPT 运行在 Docker 中，请不要使用 `localhost`，而应改为宿主机地址：

```toml
[[models.llms]]
api_base = "http://host.docker.internal:11434"  # Docker for Mac/Windows
# 或使用宿主机的实际 IP 地址
```

## 内存不足（OOM）

**现象：** `CUDA out of memory` 或 `RuntimeError: CUDA error`。

**解决方法：**

1. 改用更小的模型：

```toml
[[models.llms]]
name = "Qwen2.5-Coder-0.5B-Instruct"  # 更小的模型
```

2. 启用量化：

```bash
dbgpt start worker --model_name ... --load_4bit
```

3. 限制 GPU 使用：

```bash
CUDA_VISIBLE_DEVICES=0 uv run dbgpt start webserver ...
```

4. 或切换为 API 代理模式（无需本地 GPU）：

```toml
[[models.llms]]
provider = "proxy/openai"  # 使用远程 API，而不是本地 GPU
```

## 模型响应过慢

**现象：** 响应时间很长，或者发生超时。

**可能原因及解决方法：**

| 原因 | 解决方法 |
|---|---|
| 首次运行时模型仍在下载 | 等待下载完成（查看日志） |
| GPU 显存不足 | 使用量化或更小的模型 |
| 到 API 的网络较慢 | 检查与服务端点的连通性 |
| 上下文窗口过大 | 在配置中降低 `max_context_size` |

## Embedding 模型错误

**现象：** `Embedding model not found`，或知识库相关操作失败。

**解决方法：**

1. 确认已配置 Embedding 模型：

```toml
[[models.embeddings]]
name = "text-embedding-3-small"
provider = "proxy/openai"
api_key = "your-key"
```

2. 对于 HuggingFace Embedding，请确认模型已下载或可访问：

```toml
[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# path = "/path/to/local/model"  # 可选：本地模型路径
```

3. 如果使用本地 HuggingFace Embedding，请安装对应 extra：

```bash
uv sync --all-packages --extra "hf" --extra "cpu" ...
```

## Reranker 不生效

**现象：** 启用 reranker 后，RAG 效果没有改善。

**解决方法：**

确认在 TOML 中已配置 reranker：

```toml
[[models.rerankers]]
name = "BAAI/bge-reranker-base"
provider = "hf"
```

或者使用 SiliconFlow：

```toml
[[models.rerankers]]
name = "BAAI/bge-reranker-v2-m3"
provider = "proxy/siliconflow"
api_key = "${env:SILICONFLOW_API_KEY}"
```

## 还是没解决？

- 查看 [LLM FAQ](/docs/faq/llm)
- 参考 [Model Providers](/docs/getting-started/providers/) 文档
- 搜索 [GitHub Issues](https://github.com/eosphoros-ai/DB-GPT/issues)
