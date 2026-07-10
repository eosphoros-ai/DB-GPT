# 🚀 DB-GPT V0.8.1 — 让 AI 数据助理走向生产：定时、连接与长程 Agent

V0.8.1 延续 V0.8.0 AI 数据助理的方向，把“一次性完成分析”的能力进一步沉淀为**可调度、可连接、可观察、可运维**的生产化工作流。

## 简介

DB-GPT V0.8.0 完成了从“对话问答”到“任务交付”的范式跃迁。V0.8.1 则面向真实团队的持续使用场景，回答几个更偏生产化的问题：

- 一次成功的数据分析很有价值，如何**按周期重复执行**，而不必每次重新对话？
- 只连接数据库的 Agent 能力有限，如何让它**安全接入外部系统与业务工具**？
- 复杂分析往往会运行很多步，如何让它**稳定控制上下文窗口**，并让用户**看清楚它在做什么**？
- 生产数据库 Schema 庞大，如何让连接器构建、Schema 索引和向量检索**更快、更可靠**？

围绕这些问题，本版本引入了**定时任务（Scheduled Tasks）**、**MCP 连接器（MCP Connectors）**、**上下文管理与任务计划追踪**，同时扩展模型、数据源、向量存储和缓存生态，并补充一批面向生产环境的性能、安全与兼容性修复。

V0.8.1 的核心价值可以概括为：让 AI 数据助理从“能完成一次复杂分析”，进一步走向“能被团队反复使用、持续运行和稳定运维”。

### 关键特性速览

- ⏰ **定时任务** — 将已完成的对话保存为周期性任务，按 Cron 计划重放 Agent 流程
- 🔌 **MCP 连接器** — 通过 Model Context Protocol 将 Agent 接入外部工具，支持内置模板与自定义 MCP Server
- 🧠 **上下文管理与任务计划追踪** — 帮助长程 ReAct/Data Agent 任务控制上下文窗口，并在前端展示执行进度
- 🚀 **数据源连接器缓存** — 对昂贵的连接器构建过程增加 TTL 缓存，大 Schema 场景下热缓存查询从约 63s 降至 10ms 以内
- 🧱 **生态扩展** — 新增 LiteLLM、Qdrant、Valkey（缓存 + 向量）、openGauss、StarRocks 二进制类型、DeepSeek V4 Pro 和 MiniMax-M3
- 🛡️ **安全与稳定性加固** — 收紧配置文件权限、校验上传文件名、限制个人 Skill 执行，并提升索引容错能力

## 核心特性

### ⏰ 定时任务：把一次成功分析变成持续产出

很多数据分析工作天然是周期性的：每日经营日报、每周风险检查、月度财务摘要，或基于最新数据库快照反复执行的诊断分析。V0.8.1 引入**定时任务（Scheduled Tasks）**，让一次成功的分析对话可以沉淀为可重复执行的任务。

你只需先完成一次数据分析，再将该对话保存为任务。DB-GPT 会按 Cron 计划重放完整的 ReAct Agent 流程，每次运行都会生成新的对话与报告，并保留完整执行历史，方便审计、复盘和团队共享。

#### 将对话保存为周期性任务

- **一键保存已完成对话**：将任意完成的分析对话转化为定时任务。
- **灵活设置调度周期**：支持每小时、每天、每周、每月，或自定义 Cron 表达式。
- **冻结执行上下文**：原始问题、模型、已选 Skill 和连接器环境会写入任务快照，使每次重放都在相同条件下运行。
- **启停任务**：可在定时任务页面直接暂停或重新启用任务。

<img alt="保存对话为定时任务" src="/img/schedule/save_schedule_task_zh.png" width="720px" />

#### 运行历史与只读回放

每一次定时运行都会记录状态、耗时、结果摘要，以及它生成的对话 ID。你可以打开任意一次历史运行，直接从历史记录中回放该次对话；回放不会再次触发 LLM 调用，让复盘既低成本又可复现。

<img alt="定时任务列表" src="/img/schedule/schedule_task_list_zh.png" width="720px" />

<img alt="定时任务运行详情" src="/img/schedule/schedule_task_info_zh.png" width="720px" />

### 🔌 MCP 连接器：让 Agent 安全接入外部工具

V0.8.1 通过 **MCP 连接器（MCP Connectors）** 将 DB-GPT Agent 的能力从数据库和本地 Skill 扩展到外部服务。Agent 现在可以通过 Model Context Protocol 接入外部工具，同时由用户掌控每次会话到底挂载哪些连接器。

当前内置连接器模板包括飞书、钉钉、语雀、GitHub、Notion、Linear、Tavily 和 DeepWiki。你也可以接入任意支持 SSE 或 Streamable HTTP 的自定义 MCP Server。

#### 面向 Agentic 工作流的外部工具接入

| 能力 | 说明 |
| --- | --- |
| 内置模板 | 覆盖沟通协作、文档、项目管理、搜索和开发者工具等场景 |
| 自定义 MCP Server | 可配置服务端点、传输协议和认证方式 |
| 按会话选择连接器 | Agent 只会获得当前任务相关的工具，减少干扰与 Token 消耗 |
| 工具透明可见 | 可查看每个连接器暴露的工具名称、描述和输入参数 |
| 人工确认机制 | 内置连接器中的写操作会先弹出确认，再真正执行 |
| 凭据加密存储 | 连接器凭据加密保存在 DB-GPT 元数据库中，并在服务重启后自动恢复 |

<img alt="MCP 连接器列表" src="/img/mcp/mcp_list_zh.png" width="720px" />

<img alt="MCP 连接器工具列表" src="/img/mcp/mcp_tool_list_zh.png" width="720px" />

### 🧠 上下文管理与任务计划追踪：让长程任务更稳定、更透明

Agentic 数据分析往往不是一个短对话，而是需要多步探索、反复尝试、生成中间产物的长程任务。V0.8.1 为 ReAct/Data Agent 流程新增上下文管理与任务计划追踪，让长任务更稳定，执行过程也更易理解。

- **多层上下文压缩**：帮助长任务避免超过模型上下文窗口。
- **实时上下文使用事件**：将上下文窗口使用情况实时推送到前端。
- **任务计划追踪**：Agent 维护结构化 Todo 列表，并在步骤推进时推送计划更新。
- **更清晰的动作解释**：每一步动作都会展示它在做什么，以及为什么需要执行。
- **前端任务计划卡片与上下文使用指示器**：让整个执行过程透明可见。

<img alt="上下文使用状态与任务计划追踪" src="/img/context/context_task_plan_zh.png" width="720px" />

<img alt="前端任务计划 Todo 列表" src="/img/context/todowrite_zh.png" width="720px" />

<img alt="上下文窗口使用指示器" src="/img/context/context_used.png" width="720px" />

在底层，`ContextManager` 编排一套由 Token 预算状态驱动的**渐进式多层压缩**机制。随着用量越过警告与错误阈值，压缩力度逐级增强：从截断早期 Observation，到丢弃早期轮次，再到由 LLM 生成结构化摘要；若模型仍报 `context_too_long`，还有应急兜底层。

这些改进让 DB-GPT 更适合承接需要多步推理、反复尝试和中间产物管理的复杂数据分析工作流。

### 🧱 模型、数据源与存储生态扩展

V0.8.1 进一步扩展了 DB-GPT 周边生态，让团队可以更方便地复用已有模型、数据库、向量存储和缓存基础设施。

#### LiteLLM 嵌入式 AI Gateway

DB-GPT 新增 **LiteLLM** 作为嵌入式代理 Provider，注册名为 `proxy/litellm`。它不是一个额外的代理服务，而是 DB-GPT 进程内直接调用 LiteLLM，让你通过统一入口访问 OpenAI、Anthropic、Vertex AI、Bedrock、Azure、Cohere、Mistral、Groq、Ollama 等 LiteLLM 支持的众多后端。

```toml
[[models.llms]]
name = "anthropic/claude-3-5-sonnet-20241022"
provider = "proxy/litellm"
```

#### 新增向量检索与缓存后端

- **Qdrant 向量检索**：支持高性能向量搜索场景。
- **Valkey 向量存储**：支持使用 Valkey 和 `valkey-search` 构建向量检索链路。
- **Valkey 缓存存储**：支持 LLM 响应缓存和 Embedding 缓存场景。
- **可配置距离度量**：向量检索的距离度量可按需配置。
- **Valkey 向量客户端 `CLIENT SETNAME`**：使 DB-GPT 的连接在 Valkey 监控工具中可被清晰识别。

#### 新增数据源与模型支持

- **openGauss 数据源**：补充连接、展示和使用文档支持。
- **StarRocks `VARBINARY` 与 `BINARY` 类型**：完善 StarRocks 类型兼容。
- **MiniMax-M3**：升级为 MiniMax Provider 默认模型，同时保留 MiniMax-M2.7 可选。
- **DeepSeek V4 Pro**：新增模型支持。

### 🚀 性能优化：面向大 Schema 和生产库的关键改进

V0.8.1 针对大 Schema、生产级数据库和索引链路做了重要性能优化。

- **数据源连接器缓存**：`ConnectorManager.get_connector(db_name)` 现在对构建好的连接器增加 TTL 缓存。在近 900 张表的生产 SQL Server 场景中，热缓存连接器查询从约 **63 秒降至 10ms 以内**。
- **按数据库粒度的索引锁**：避免 Schema 索引与刷新操作并发竞争，降低产生空索引的风险。
- **按 Chunk 粒度容错**：单个异常 Embedding Chunk 不再导致整个索引任务失败。
- **MSSQL 元数据兼容**：针对 SQL Server 使用正确的 `INFORMATION_SCHEMA` 与扩展属性查询字段元数据。
- **Milvus 2.5+ 兼容**：提升 Milvus 向量存储在新版本下的兼容性。

### 🛡️ 安全与稳定性加固

本版本还包含多项面向生产环境的安全与稳定性增强：

- `~/.dbgpt/configs/<profile>.toml` 本地 Profile 配置文件写入权限收紧为 `0o600`。
- 知识库模块接口补充认证依赖。
- 更严格校验 Skill 上传文件名、示例文件名和 Python 上传文件名。
- 限制个人 Skill 脚本执行，降低未受控执行风险。
- Code Interpreter 临时脚本写入时显式使用 UTF-8 编码。
- Markdown 知识库默认使用 size chunking，索引过程更可预测。
- ReAct 解析器更好地兼容多步输出。
- Chat DB 提示词明确说明当前检索到的表结构是 TOP-K 子集，提升全库元问题的回答准确性。

## 功能增强

- 支持定时任务与 MCP 连接器（[#3095](https://github.com/eosphoros-ai/DB-GPT/pull/3095)）
- 新增上下文管理、任务计划追踪及对应前端 UI（[#3053](https://github.com/eosphoros-ai/DB-GPT/pull/3053)）
- 新增 LiteLLM 嵌入式 AI Gateway Provider（[#3043](https://github.com/eosphoros-ai/DB-GPT/pull/3043)）
- 新增 Qdrant 向量检索支持（[#3034](https://github.com/eosphoros-ai/DB-GPT/pull/3034)）
- 新增 Valkey 向量存储集成（[#3051](https://github.com/eosphoros-ai/DB-GPT/pull/3051)）
- 新增 Valkey 缓存存储集成（[#3057](https://github.com/eosphoros-ai/DB-GPT/pull/3057)）
- 为 Valkey 向量客户端增加 `CLIENT SETNAME`（[#3090](https://github.com/eosphoros-ai/DB-GPT/pull/3090)）
- 支持配置向量检索距离度量（[#3044](https://github.com/eosphoros-ai/DB-GPT/pull/3044)）
- 为 `ConnectorManager.get_connector` 增加 TTL 缓存（热缓存约 63s → 10ms 以内）（[#3046](https://github.com/eosphoros-ai/DB-GPT/pull/3046)）
- 新增 openGauss 数据源支持（[#3007](https://github.com/eosphoros-ai/DB-GPT/pull/3007)）
- 为 StarRocks 实现 `VARBINARY` 和 `BINARY` 类型（[#3062](https://github.com/eosphoros-ai/DB-GPT/pull/3062)）
- MiniMax 默认模型升级到 M3（[#3093](https://github.com/eosphoros-ai/DB-GPT/pull/3093)）
- 加强 `~/.dbgpt/configs/<profile>.toml` 文件权限为 `0o600`（[#3077](https://github.com/eosphoros-ai/DB-GPT/pull/3077)）

## 问题修复

- 修复 Web UI 创建 DuckDB 数据源的问题（[#3009](https://github.com/eosphoros-ai/DB-GPT/pull/3009)）
- 支持 DeepSeek V4 Pro（[#3079](https://github.com/eosphoros-ai/DB-GPT/pull/3079)）
- Markdown 知识库默认使用 size chunking（修复 [#3030](https://github.com/eosphoros-ai/DB-GPT/issues/3030)）（[#3033](https://github.com/eosphoros-ai/DB-GPT/pull/3033)）
- 限制个人 Skill 脚本执行（[#3071](https://github.com/eosphoros-ai/DB-GPT/pull/3071)）
- 校验示例文件名（[#3066](https://github.com/eosphoros-ai/DB-GPT/pull/3066)）
- 校验 Skill 上传文件名（[#3065](https://github.com/eosphoros-ai/DB-GPT/pull/3065)）
- 约束 Python 上传文件名（[#3064](https://github.com/eosphoros-ai/DB-GPT/pull/3064)）
- 处理知识空间 ID 响应（[#3070](https://github.com/eosphoros-ai/DB-GPT/pull/3070)）
- 兼容多步 ReAct 输出（[#3074](https://github.com/eosphoros-ai/DB-GPT/pull/3074)）
- 告知 LLM 当前表列表是 TOP-K 子集，而非全库表列表（[#3045](https://github.com/eosphoros-ai/DB-GPT/pull/3045)）
- 扩展 `gpts_messages.content` 字段以容纳更长的 Agent 消息（[#3055](https://github.com/eosphoros-ai/DB-GPT/pull/3055)）
- 兼容 Milvus 2.5+（[#3042](https://github.com/eosphoros-ai/DB-GPT/pull/3042)）
- 增加按 Chunk 粒度容错和按数据库粒度索引锁（[#3040](https://github.com/eosphoros-ai/DB-GPT/pull/3040)）
- 为 MSSQL `get_fields()` 实现 SQL Server 兼容的 `INFORMATION_SCHEMA` 查询（[#3039](https://github.com/eosphoros-ai/DB-GPT/pull/3039)）
- 为知识库模块接口补充认证依赖（[#3038](https://github.com/eosphoros-ai/DB-GPT/pull/3038)）
- 修复 BranchOperator 错误跳过共享下游节点的问题（修复 [#2935](https://github.com/eosphoros-ai/DB-GPT/issues/2935)）（[#3035](https://github.com/eosphoros-ai/DB-GPT/pull/3035)）
- 遵循已配置的通义 Embedding 模型名称（修复 [#3029](https://github.com/eosphoros-ai/DB-GPT/issues/3029)）（[#3032](https://github.com/eosphoros-ai/DB-GPT/pull/3032)）
- 写入 Code Interpreter 临时脚本时显式使用 UTF-8 编码（[#3023](https://github.com/eosphoros-ai/DB-GPT/pull/3023)）

## 升级指南

本指南适用于从 **v0.8.0** 升级到 **v0.8.1**。

V0.8.1 的元数据变更为 1 个字段变更 + 3 张新增表。升级脚本已提供在 `assets/schema/upgrade/v0_8_1/` 目录下：

- `upgrade_to_v0.8.1.sql`：在 v0.8.0 数据库基础上执行的增量脚本。
- `v0.8.1.sql`：用于全新安装的完整 v0.8.1 Schema。

> 与历史版本一致，增量脚本面向 MySQL。SQLite 用户请按惯例在升级前备份元数据库，新增表会在服务启动时自动创建。

### 准备工作

#### 备份数据库

:::warning
为避免数据丢失，升级前请务必备份元数据库。请根据数据库类型选择合适的备份方式，例如 MySQL 使用 `mysqldump`，SQLite 直接复制数据库文件。
:::

### 升级数据库

V0.8.1 升级包含 1 个字段变更和 3 张新增元数据表：

| 变更 | 说明 |
| --- | --- |
| `gpts_messages.content` → `longtext` | 支持更长的 Agent 消息和执行轨迹。 |
| `connector_instance` | 存储 MCP 连接器实例、加密凭据、传输/扩展配置和生命周期状态。 |
| `dbgpt_serve_scheduled_task` | 存储定时任务定义、Cron 表达式和冻结的对话快照。 |
| `dbgpt_serve_scheduled_run` | 存储定时任务运行历史：状态、摘要、错误信息和输出对话 ID。 |

对 MySQL 元数据库执行增量脚本：

```bash
mysql -u <user> -p dbgpt < assets/schema/upgrade/v0_8_1/upgrade_to_v0.8.1.sql
```

### 安装依赖

请根据你的部署方式安装或更新依赖。如果使用源码方式和默认配置安装：

```bash
uv sync --all-packages
```

如需使用可选集成，请按需安装对应 Extra：

```bash
# LiteLLM 代理 Provider
uv sync --all-packages --extra "proxy_litellm"

# Qdrant 向量存储
uv sync --all-packages --extra "storage_qdrant"

# Valkey 缓存 / 向量存储
uv sync --all-packages --extra "storage_valkey"
```

### 重启 DB-GPT

使用你原来的启动方式重启 DB-GPT 服务。启动后建议验证：

- 历史对话可以正常加载。
- MCP 连接器页面可以正常展示、激活和测试连接器。
- 定时任务可以从已完成对话保存，并能展示运行历史。
- 长程 ReAct/Data Agent 对话可以正常展示任务计划和上下文使用状态。

## 参考链接

- [DB-GPT V0.8.0 发版说明](http://docs.dbgpt.cn/docs/next/changelog/Released_V0.8.0)
- [快速开始](http://docs.dbgpt.cn/docs/overview/)
- [安装指南](http://docs.dbgpt.cn/docs/next/installation/)
- [定时任务](http://docs.dbgpt.cn/docs/next/application/scheduled_tasks)
- [MCP 连接器](http://docs.dbgpt.cn/docs/next/application/mcp_connectors)
