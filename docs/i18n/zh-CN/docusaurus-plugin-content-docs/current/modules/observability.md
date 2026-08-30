# 可观测性

DB-GPT 可观测性（Observability）为 Agent 的执行过程提供端到端的可视化洞察——它在思考什么、调用了哪些工具、模型消耗了多少 Token、每一步耗时多少。它回答「Agent 到底做了什么」这个问题，无需切换到外部链路追踪系统。

## 核心能力

### 总览看板（Overview）

总览页（`/observability`）提供最近 24 小时的整体健康快照：

- **KPI 卡片** —— Agent 数量、事件数、Token 消耗总量、P95 延迟、错误率。
- **Token 明细** —— 输入 Token、输出 Token、缓存命中 Token、缓存未命中 Token，汇总你的 Agent 运行所消耗的模型用量。
- **模型使用明细表** —— 按模型聚合：调用次数、输入/输出 Token、总 Token、平均延迟。
- **趋势图** —— 事件量与 P95 延迟随时间的变化。
- **Agent 健康** —— 每个 Agent 的事件数与错误率。

### 链路列表与链路详情

- **链路列表**（`/observability/traces`）把每次 Agent 执行列成一条 trace，并过滤掉纯 HTTP 噪音，只展示有意义的 Agent 链路。
- **链路详情**（`/observability/traces/{trace_id}`）展示完整执行链：
  - 对话 ID（可追溯到来源对话），
  - 可折叠的 span 树，包含 `span_id` / `parent_span_id`、agent、模型、成本、耗时与原始元数据。

### 对话内 Trace 标签页

在对话会话中，右侧面板的 **Trace** 标签页把当前对话的执行过程渲染成一条**消息流时间线**：

```
用户问题 → 系统提示词 → 思考 → 工具调用（输入 + 输出）→ 回复
```

它还原了消息发送给模型时的形态——任务预览、推理、每次工具调用及其返回结果——以连续流的形式呈现，而不是扁平的 span 树。

## 工作原理

可观测性建立在一个可插拔的读侧协议之上——`ObservabilityProvider`：

- **默认后端（SQLite）** —— 开箱即用，零外部依赖。Span 与事件写入独立的 `logs/observability.db` 文件，因此高吞吐的遥测数据不会撑爆主业务数据库。
- **可扩展** —— 后端通过配置（`provider_cls`）选择，未来可无缝接入其他后端（如 ZizkaDB、OpenTelemetry、Prometheus），而无需改动 UI。

写侧复用现有的 `root_tracer` span。每一次 Agent 轮次、LLM 调用、工具执行都会成为一个 span，携带模型名、Token 用量（prompt / completion / total）、延迟、成本与状态。每条消息通过 `trace_id` 关联到其 trace，从而把对话对应到它的执行链路。

## 关键收益

- **零配置可见性** —— 基于默认 SQLite 后端运行，无需额外服务。
- **可追溯** —— 从一条聊天回复，下钻到背后的具体工具调用、模型 Token 与延迟。
- **成本与延迟感知** —— 一眼看清 Token 消耗与 P95 延迟。
- **可插拔** —— 通过配置切换后端，无需改动 UI 页面。