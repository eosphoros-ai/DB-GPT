---
title: 上下文管理
---

# Agent 上下文管理

Agent 上下文管理用于让长时间运行的 ReAct 对话稳定保持在模型上下文窗口内，同时尽量不丢失任务状态。它会在每次调用模型前统计 token 使用量，向前端发送实时上下文状态，并在对话变长时按层级逐步压缩。

## 总览

```text
用户任务
   |
   v
Agent 构造消息
system prompt + task progress + memory + 最近 ReAct 轮次
   |
   v
统计 token
ProxyTokenizerWrapper.count_token(model_name)
兜底估算：len(content) // 4
   |
   v
计算预算
effective_budget = max_context_tokens - reserved_tokens
usage_ratio = used_tokens / effective_budget
   |
   v
判断状态
normal < warning < error < critical < overflow
   |
   +-- normal --------------------------------------+
   |                                                |
   v                                                |
发送消息给 LLM                                    |
                                                    |
warning 及以上                                     |
   |                                                |
   v                                                |
第 1 层：Observation 微压缩                        |
截断较旧的工具观察结果                             |
   |                                                |
   v                                                |
重新统计并发送 context.status                      |
   |                                                |
   +-- 低于 warning -------------------------------+
   |                                                |
   v                                                |
第 2 层：Session memory 压缩                       |
丢弃较旧 ReAct 轮次，保留最近轮次                  |
   |                                                |
   v                                                |
重新统计并发送 context.status                      |
   |                                                |
   +-- 低于 error ---------------------------------+
   |                                                |
   v                                                |
第 3 层：完整上下文压缩                            |
用 LLM 总结旧轮次                                  |
   |                                                |
   v                                                |
重新统计并发送 context.status                      |
   |                                                |
   +----------------------------------------------->+

如果模型仍然返回上下文溢出错误：

LLM context_too_long / maximum context length error
   |
   v
第 4 层：Reactive 压缩
保留 system prompt + 最后 2 个 ReAct 轮次
   |
   v
用压缩后的消息重试一次模型调用
```

工具结果会通过单独的快照路径保留：

```text
Action 执行成功
   |
   v
写入完整操作快照
step、action、action_input、observation、thought、timestamp
   |
   v
把 snapshot path 存到 memory fragment
以及 task progress metadata
   |
   v
未来重建 memory prompt
Observation: 短观察结果或已压缩观察结果
[Full detail available at: /path/to/snapshot.json]
   |
   v
第 1 层 / 第 2 层可以缩小 prompt 文本
但不会删除原始工具结果文件
```

## Token 预算

上下文管理器会在模型调用前统计当前 `AgentMessage` 列表的 token 数。统计逻辑使用 `ProxyTokenizerWrapper`，并传入当前 `model_name`。如果 tokenizer 无法统计，则退化为粗略估算：每 4 个字符按 1 个 token 计算。

可用上下文窗口计算方式：

```text
effective_budget = max_context_tokens - reserved_tokens
```

`reserved_tokens` 用于为模型输出预留空间，避免 prompt 本身占满整个模型窗口。

## 状态与阈值

| 状态 | 默认触发条件 | 含义 |
| --- | --- | --- |
| `normal` | `< 70%` | 不压缩。 |
| `warning` | `>= 70%` | 开始轻量压缩。 |
| `error` | `>= 90%` | 必要时使用 LLM 总结压缩。 |
| `critical` | `>= 95%` | 与 error 类似，但表示更紧急。 |
| `overflow` | `>= 100%` | prompt 超过有效预算。 |

每次统计和每层压缩后，后端都会发送 `context.status` 事件：

```json
{
  "type": "context.status",
  "used": 19000,
  "budget": 115904,
  "ratio": 0.164,
  "state": "normal",
  "compact_layer": null
}
```

前端会把这个事件展示为上下文窗口指示器。

## 压缩层级

### 第 1 层：Observation 微压缩

第 1 层是最轻量的压缩，只处理旧工具调用产生的 `Observation:` 消息。最近轮次会完整保留。

规则：

- 当使用率达到 `warning_threshold` 时触发。
- 超过 `max_observation_age_rounds` 的轮次会被视为旧轮次。
- 旧 Observation 会被截断到 `truncated_observation_max_chars`。
- 如果 Observation 有快照路径，压缩后的消息会保留完整详情的引用。

这一层成本低、可确定，不调用 LLM。

### 第 2 层：Session Memory 压缩

第 2 层会从 prompt 中移除旧的完整 ReAct 轮次。它依赖已经注入 system prompt 的 task-progress summary，因此 Agent 仍然知道哪些工作已经完成。

规则：

- 当第 1 层后仍然达到或超过 `warning_threshold` 时触发。
- 至少保留 `min_keep_recent_rounds` 个最近轮次。
- 同时尽量保留不少于 `min_keep_tokens` 的最近内容。
- 丢弃的是完整旧轮次，而不是任意切分单条消息。

这一层也是确定性逻辑，不调用 LLM。

### 第 3 层：完整上下文压缩

第 3 层会用 LLM 把较旧的对话轮次压缩成结构化上下文摘要，然后保留摘要和最近轮次。

规则：

- 当使用率达到或超过 `error_threshold` 时触发。
- 最近 `min_keep_recent_rounds` 个轮次原样保留。
- 更旧的消息会被总结成一条合成摘要消息。
- 摘要提示词会要求模型保留精确的任务状态、路径、数值、变量名、错误和下一步。
- 如果总结连续失败，达到 `max_compact_failures` 后会触发熔断，停止继续尝试。

这一层成本更高，但比直接丢弃旧消息更能保持语义连续性。

### 第 4 层：Reactive 压缩

第 4 层是紧急兜底路径。它不是由正常预算状态机触发，而是在模型调用返回上下文溢出错误时触发，例如 `context_too_long`、`context_length_exceeded` 或 `maximum context length`。

规则：

- 保留 system 消息。
- 只保留最后 2 个 ReAct 轮次。
- 依赖 system prompt 中的 task-progress summary 保持任务连续性。
- 用压缩后的消息重试一次模型调用。

这一层非常激进，因为它只在模型已经拒绝当前 prompt 后才使用。

## 工具结果快照

工具观察结果可能非常大：SQL 结果表、生成代码输出、解释器日志、文件路径、报告元数据和中间计算值都可能快速占满 prompt。DB-GPT 通过把完整操作详情和需要进入模型上下文的文本拆开，来保持 prompt 紧凑。

当一个 action 成功执行后，Agent 会为完整操作写入一份 JSON 快照。快照包含：

- `step`
- `action`
- `phase`
- `action_intention`
- `action_reason`
- `thought`
- `action_input`
- `observation`
- `timestamp`
- `conv_id`

默认快照目录为：

```text
$DBGPT_HOME/workspace/op_snapshots/<conv_id>/
```

如果设置了 `AgentContext.output_dir`，DB-GPT 会优先使用该目录。

快照文件名由步骤和 action 组成：

```text
step_003_sql_query.json
step_006_code_interpreter.json
```

快照路径会挂到内存中的 `AgentMemoryFragment` 上，也会记录到 task-progress metadata 中。当 Agent 后续把 memory 重建为 prompt 消息时，会附加一条轻量引用：

```text
Observation: <observation text>
[Full detail available at: /path/to/step_003_sql_query.json]
```

这对压缩很重要：

- 第 1 层可能会截断旧的 `Observation:` 文本，但会尽量保留快照引用。
- 第 2 层可能会把旧 ReAct 轮次从 prompt 中移除，但 task progress 仍会记录快照文件名作为引用。
- 第 3 层会总结旧消息，而原始工具结果仍然保留在磁盘上，便于精确恢复。

换句话说，压缩减少的是 prompt 负载；精确工具结果不必只存在于上下文文本里。

## 配置

可以在应用 TOML 文件中配置 Agent 上下文管理：

```toml
[service.web.agent_context]
max_context_tokens = 120000
reserved_tokens = 4096
warning_threshold = 0.70
error_threshold = 0.90
critical_threshold = 0.95
min_keep_recent_rounds = 3
max_observation_age_rounds = 5
truncated_observation_max_chars = 200
min_keep_tokens = 10000
max_compact_failures = 3
```

为了让行为稳定，建议在每个 LLM 部署配置中显式设置 `context_length`，这样模型 metadata 也会反映真实的 provider 上下文窗口：

```toml
[[models.llms]]
name = "Qwen/Qwen2.5-Coder-32B-Instruct"
provider = "proxy/siliconflow"
api_key = "${env:SILICONFLOW_API_KEY}"
context_length = 32768
```

这样切换模型时，上下文预算也会跟随模型能力自动变化。

## 设计说明

- 第 1 层和第 2 层都是确定性、低成本压缩，优先于 LLM 总结。
- 第 3 层只在上下文接近失败时调用 LLM。
- 第 4 层是模型侧上下文溢出错误后的最后重试路径。
- 前端独立接收 `context.status` 事件，因此上下文窗口指示器可以实时更新，不会污染正常对话内容。
- 压缩是渐进式的：每一层后都会重新统计 token，如果 prompt 已回到安全状态，就不会继续升级到更强压缩。
