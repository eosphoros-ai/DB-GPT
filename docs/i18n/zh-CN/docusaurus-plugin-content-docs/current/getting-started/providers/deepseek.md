---
sidebar_position: 2
title: DeepSeek
---

# DeepSeek

配置 DB-GPT 使用 DeepSeek 的语言模型进行聊天与推理。

## 前置条件

- 一个可用的 [DeepSeek API key](https://platform.deepseek.com/)
- 已安装带 `proxy_openai` 扩展的 DB-GPT

## 安装依赖

```bash
uv sync --all-packages \
  --extra "base" \
  --extra "proxy_openai" \
  --extra "rag" \
  --extra "storage_chromadb" \
--extra "dbgpts"
```

:::info Embedding 模型
DeepSeek 本身不提供 embedding 模型。默认配置使用 HuggingFace embedding 模型（`BAAI/bge-large-zh-v1.5`）。如果使用该方案，还需要额外安装：

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

## 配置方式

编辑 `configs/dbgpt-proxy-deepseek.toml`：

```toml
[models]
[[models.llms]]
name = "deepseek-v4-pro"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"
# 为严格的 ReAct 输出解析关闭 V4-Pro 思考模式。
thinking_enabled = false

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# Uncomment to use a local model path:
# path = "models/bge-large-zh-v1.5"
```

## 可用模型

| 模型 | 配置名 | 说明 |
|---|---|---|
| DeepSeek-V4-Pro | `deepseek-v4-pro` | 1M 上下文，适合高级推理、代码与 Agent 任务 |
| DeepSeek-R1 | `deepseek-reasoner` | 推理能力强，适合复杂思考任务 |
| DeepSeek-V3 | `deepseek-chat` | 通用聊天与问答 |

ReAct Agent 使用 `deepseek-v4-pro` 时建议保留 `thinking_enabled = false`。
DeepSeek V4-Pro 默认开启思考模式，可能在严格的
`Thought/Action/Action Input` 输出格式前产生推理块，导致解析失败。

## 启动服务

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```

## 故障排查

| 问题 | 解决方法 |
|---|---|
| `AuthenticationError` | 到 [platform.deepseek.com](https://platform.deepseek.com/) 检查 API key 是否正确 |
| Embedding 下载慢 | 预先下载模型，或使用镜像源（如 `UV_INDEX_URL`） |
| Embedding 内存不足 | 增加 `--extra "cpu"`，让 embedding 在 CPU 上运行 |

## 下一步

- [Getting Started](/docs/getting-started/quick-start) —— 查看完整首跑流程
- [Model Providers](/docs/getting-started/providers/) —— 继续查看其他提供方
