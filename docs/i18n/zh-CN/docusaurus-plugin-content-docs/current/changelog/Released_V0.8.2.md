# 🚀 DB-GPT V0.8.2 — 更完整的 Agentic 数据工作流：多文件分析、知识检索与并行子 Agent

在复杂的数据分析任务中，业务信息往往分散在多份文件和知识库中；分析过程既包含可以并行推进的工作，也包含必须由业务人员确认的关键条件。当文件处理、知识检索、任务执行与人工确认彼此割裂时，Agent 难以保持完整上下文，分析流程容易被反复中断。

V0.8.2 围绕这类端到端任务，完善了从输入、检索、执行到确认的工作链路：多文件 Agentic 分析统一管理关联输入，Agentic 知识库检索支持在任务过程中持续查找所需信息，并行子 Agent 委派同时推进彼此独立的工作，人在回路（Human-in-the-Loop）交互式追问补齐必须由用户判断的关键条件。

### 关键特性速览

- 📎 **多文件上传数据分析** — 在一个会话中上传、预览多个文件，并作为同一个任务上下文使用
- 🔎 **Agentic 知识库检索** — Agent 可以迭代浏览、搜索和读取知识来源，而不是依赖单轮召回
- 🧩 **并行子 Agent 委派** — 并发执行彼此独立的分析，并展示每个子任务的进度与产物
- 🙋 **人在回路交互式追问** — 当需求或选项不明确时，Agent 可以暂停并请求结构化输入
- 🛡️ **安全与稳定性加固** — 在沙箱环境中渲染 Jinja2 模板、限制上传路径、消除 macOS TTS 的 Shell 注入风险，并提升客户端、存储和 RAG 稳定性

## 核心特性

### 📎 多文件分析：把一组文件作为同一个任务上下文

数据任务往往从一组相关文件开始，而不是一张孤立的表格：订单表与客户表、连续几个月的导出数据，或一份报告及其支撑材料。V0.8.2 支持在同一个对话中附加多个文件，并在后续执行中持续将它们作为任务上下文使用。

#### 在输入区上传、预览和管理文件

- **一次添加多个文件**：通过文件选择器批量选择，或直接拖拽到输入区。
- **独立跟踪每个文件**：分别展示上传、检查、就绪和失败状态。
- **执行前预览**：在限定范围内预览表格或文档；如果只展示部分内容，界面会明确标识。
- **在对话过程中增删附件**：无需重新上传其余文件。
- **遵循服务端下发的限制配置**：文件数量、大小、并发数、超时与扩展名均可由部署方调整。

默认支持的文件类型包括 CSV、TSV、Excel、JSON/JSONL、Parquet、PDF、Word、PowerPoint、Markdown 和纯文本文件。能否预览某个文件，取决于部署环境是否安装了对应的可选解析依赖。

<img alt="将多个文件拖拽到 AI 数据助手" src="/img/agentic-multi-file/multi-file-drag-and-drop-zh.jpg" width="720px" />

<img alt="在开始多文件分析前预览文件" src="/img/agentic-multi-file/file-preview-zh.jpg" width="720px" />

#### 联合分析多个文件

Agent 接收的是稳定的文件 ID，而不是服务端存储路径。文件归属于当前用户和对话，仅在执行工具需要时才会写入执行工作区。这样，`load_file`、Code Interpreter 和分析工具可以共同处理所选文件，同时不暴露实际存储位置。

当包含附件的对话被保存为定时任务时，DB-GPT 会冻结一份任务级文件副本。每次定时运行都基于同一份文件快照重放，不依赖可能已变化的会话上传文件。

<img alt="围绕多个已附加文件提问并查看分析结果" src="/img/agentic-multi-file/multi-file-analysis-zh.jpg" width="720px" />

### 🔎 Agentic 知识库检索：把检索变成可迭代的过程

传统 RAG 通常只执行一次检索，随后组装 Prompt 生成答案。这种方式适合简单问题，但当首轮查询不够准确，或证据分散在多个来源时，模型缺少继续查找和修正的空间。

V0.8.2 将知识库对话调整为 Agentic 循环：Agent 可以先查看知识空间，改写或缩小查询范围，多次检索，打开相关文件，并在证据充分时停止。知识库专用对话配备一组更聚焦的工具，包括语义检索、文件列表、`glob`、`grep` 和文件读取，减少无关工具的干扰。

<img alt="Agent 在多轮检索中调用知识库工具，并在右侧面板展示参考来源" src="/img/knowledge/knowledge_chat_zh.jpg" width="720px" />

#### 索引方式与结构视图

| 能力 | 使用方式 |
| --- | --- |
| 向量检索 | 基于 Embedding Chunk 的语义相似度检索 |
| 文件与精确检索 | 在所选知识空间内匹配文件、检索关键词并按范围读取文件 |
| 知识图谱 | 在图谱已完成构建时提供实体与结构关系 |
| 结构视图 | 在查询阶段重建标题层级与父子上下文 |
| 代码图谱 | 构建完成后，为代码检索建立仓库、文件和符号定义索引 |

知识空间配置提供 `VectorStore`、`FullText` 和 `KnowledgeGraph` 三种索引方式选项。Git 仓库作为知识来源时支持全量与增量同步；当 Git 仓库或代码文件完成 Code Graph 构建后，可以按仓库、文件、类和函数等结构检索代码。

<img alt="创建知识库时选择向量索引、结构索引和图索引" src="/img/knowledge/knowledge_create_zh.jpg" width="720px" />

当检索结果超出上下文容量时，Agent 可以先将结果持久化，再按需分段读取。引用信息与最终答案分离，以结构化数据传递给前端展示，便于核对来源。

<img alt="带引用编号与参考来源面板的 Agentic 知识库回答" src="/img/knowledge/knowledge_reference_chat_zh.jpg" width="720px" />

### 🧩 并行子 Agent：让独立任务并发执行

复杂任务经常包含若干彼此独立的分支，例如分别分析多份数据集、比较多种候选方案，或分别排查若干相互独立的原因，再汇总为一个结论。V0.8.2 支持主 Agent 将这些分支委派给子 Agent 并发执行。

主 Agent 会先记录任务计划，再将独立工作项下发给子 Agent。每个子 Agent 都有自己的上下文、记忆、对话和工作目录；它可以继承主任务的数据库、知识库和只读工具访问权限，但不能递归委派任务。

| 能力 | 说明 |
| --- | --- |
| 有界并发 | 默认单次委派最多运行 3 个子 Agent，限制可以配置 |
| 实时进度 | 向前端持续传递运行中、已完成、失败和超时状态 |
| 过程可检查 | 展示每个子 Agent 的目标、已验证步骤、输出和产物 |
| 统一汇总 | 将结构化结果返回主 Agent，生成一个综合回答 |
| 执行约束 | 保持有依赖关系的任务串行执行，并禁止子 Agent 递归委派 |

单次委派上限可以通过 `service.web.agent_context.max_parallel_subagents` 或 `DBGPT_MAX_PARALLEL_SUBAGENTS` 配置。提高该数值也会增加并发模型调用和 Token 消耗。

当工作项真正独立时，并行委派可以减少不必要的串行等待；它不会改变存在前后依赖的步骤顺序。

<img alt="并行子 Agent 任务总览：两个子任务均已完成" src="/img/agentic_data/parallel_subagent_list_zh.png" width="720px" />

<img alt="运行中的子 Agent 详情：展示目标与执行步骤" src="/img/agentic_data/parallel_subagent_detail_zh.png" width="720px" />

<img alt="已完成子 Agent 的执行记录与查询结果" src="/img/agentic_data/parallel_subagent_info_zh.png" width="720px" />

### 🙋 人在回路交互式追问：先澄清，再继续执行

有些任务如果缺少用户选择，就无法可靠完成：采用哪一种指标口径、使用哪个日期范围、是否纳入含义不明确的字段、希望使用哪种输出格式。V0.8.2 为这些场景增加了统一的交互式追问流程。

Agent 可以暂停执行，展示一个或多个结构化问题，并在用户回复后于同一次运行中恢复执行。前端支持单选、多选、自定义输入、确认与取消。等待设有超时时间，避免用户离开后任务一直处于未结束状态。

<img alt="交互式问题面板：单选项、自定义输入与确认/取消" src="/img/agentic_data/ask_user.png" width="720px" />

### 🛡️ 安全与稳定性加固

V0.8.2 收紧了 Agentic 工作流涉及的若干边界：

- 文件上传接口校验用户身份，并确保解析后的路径位于受管上传目录内。
- macOS 语音播报（TTS）不再经过 Shell 解释执行，消除命令注入风险。
- Agent 使用的 Jinja2 模板在沙箱环境中渲染。
- CORS 允许来源可以配置，并修正通配符与凭据的组合处理。
- 只有文件名严格等于 `SKILL.md` 的文件才会被识别为 Markdown Skill。
- Agent 的引用信息改为结构化数据传递，不再拼接到答案正文中。
- MySQL 存储将较长的 Agent 消息和执行报告映射为 `LONGTEXT` 类型，避免超长内容写入失败。
- Excel 知识加载可以更可靠地处理无表头工作表和包含多个工作表的工作簿。

## 功能增强

- 新增会话级多文件上传、预览与 Agentic 分析（[#3206](https://github.com/eosphoros-ai/DB-GPT/pull/3206)）
- 新增 Agentic 知识库检索，支持索引方式配置与迭代 RAG（[#3160](https://github.com/eosphoros-ai/DB-GPT/pull/3160)）
- 新增并行子 Agent 委派与执行（[#3161](https://github.com/eosphoros-ai/DB-GPT/pull/3161)）
- 为 Agent 内置工具增加人在回路的交互式追问（[#3107](https://github.com/eosphoros-ai/DB-GPT/pull/3107)）
- 新增 OrcaRouter 代理 Provider，通过 OpenAI 兼容接口接入 OrcaRouter 模型目录（[#3186](https://github.com/eosphoros-ai/DB-GPT/pull/3186)）
- 新增基于 PyODPS SQLAlchemy Dialect 的阿里云 MaxCompute（ODPS）数据源，并支持从 Web UI 配置（修复 [#3105](https://github.com/eosphoros-ai/DB-GPT/issues/3105)）（[#3178](https://github.com/eosphoros-ai/DB-GPT/pull/3178)）

## 问题修复

- 修复 Chart 或 SQL 运行缺少 `db_name` 时触发 `KeyError` 的问题（[#3199](https://github.com/eosphoros-ai/DB-GPT/pull/3199)）
- 在 `update_flow` 的 PUT 路径中加入 Flow UID（修复 [#3193](https://github.com/eosphoros-ai/DB-GPT/issues/3193)）（[#3196](https://github.com/eosphoros-ai/DB-GPT/pull/3196)）
- MySQL ORM 为较大的 Agent 消息和执行报告使用 `LONGTEXT`（[#3189](https://github.com/eosphoros-ai/DB-GPT/pull/3189)）
- 将 `EXAMPLE_1` 数据库的创建移动到 Schema 文件末尾（[#3183](https://github.com/eosphoros-ai/DB-GPT/pull/3183)）
- 使用结构化最终答案协议，将引用信息与最终答案分离（[#3182](https://github.com/eosphoros-ai/DB-GPT/pull/3182)）
- 校验文件上传接口的用户身份，并约束解析后的路径（修复 [#3104](https://github.com/eosphoros-ai/DB-GPT/issues/3104)）（[#3184](https://github.com/eosphoros-ai/DB-GPT/pull/3184)）
- 仅将文件名严格等于 `SKILL.md` 的文件加载为 Markdown Skill（[#3175](https://github.com/eosphoros-ai/DB-GPT/pull/3175)）
- 移除 macOS TTS 的 Shell 解释，防止命令注入（修复 [#3129](https://github.com/eosphoros-ai/DB-GPT/issues/3129)）（[#3174](https://github.com/eosphoros-ai/DB-GPT/pull/3174)）
- 兼容 LLM 输出中包含多个 JSON 代码块的情况（[#3117](https://github.com/eosphoros-ai/DB-GPT/pull/3117)）
- 在沙箱环境中渲染 Agent Jinja2 模板（[#3111](https://github.com/eosphoros-ai/DB-GPT/pull/3111)）
- 避免 `inner_copy_and_install` 将构建失败报告为成功（[#3141](https://github.com/eosphoros-ai/DB-GPT/pull/3141)）
- 在存在拆分 Chunk 时正确反序列化表格 Chunk（[#3140](https://github.com/eosphoros-ai/DB-GPT/pull/3140)）
- 客户端的 `create_datasource` 和 `create_flow` 调用改用 POST，而不是 GET（[#3138](https://github.com/eosphoros-ai/DB-GPT/pull/3138)）
- 支持配置 CORS 允许来源，并修正通配符与凭据的组合处理（[#3123](https://github.com/eosphoros-ai/DB-GPT/pull/3123)）
- 修复 `StreamedBytesIO` 忽略负数读取长度、丢失 `SEEK_END` 位置的问题（[#3136](https://github.com/eosphoros-ai/DB-GPT/pull/3136)）
- 在 `VariablesProvider._convert_to_value_type` 中正确处理原生 `bool` 值（[#3135](https://github.com/eosphoros-ai/DB-GPT/pull/3135)）
- 在简化的 fsspec 路径中保留 `bucket` 名称（[#3134](https://github.com/eosphoros-ai/DB-GPT/pull/3134)）
- 在 `ExcelKnowledge._load` 中处理无表头工作表和包含多个工作表的工作簿（[#3137](https://github.com/eosphoros-ai/DB-GPT/pull/3137)）
- 修正 `TeiRerankEmbeddings._parse_results` 对空值和非列表结果的判断（[#3133](https://github.com/eosphoros-ai/DB-GPT/pull/3133)）
- 避免前端 `handleChat` 的暂时性死区问题（[#3132](https://github.com/eosphoros-ai/DB-GPT/pull/3132)）
- 允许在 TOML 配置中使用 Milvus 向量存储类型（[#3127](https://github.com/eosphoros-ai/DB-GPT/pull/3127)）

## 升级指南

本指南适用于从 **v0.8.1** 升级到 **v0.8.2**。

V0.8.2 的增量元数据脚本新增 1 张会话文件表、3 张 Code Graph 表、知识空间索引方式列，并修复了 Agent 消息列宽。升级脚本位于 `assets/schema/upgrade/v0_8_2/` 目录：

- `upgrade_to_v0.8.2.sql`：在 v0.8.1 数据库基础上执行的增量脚本。
- `v0.8.2.sql`：用于全新安装的完整 v0.8.2 Schema。

> 与历史版本一致，增量脚本面向 MySQL。SQLite 用户请在升级前备份元数据库；由 ORM 管理的表会在服务启动时创建。

### 准备工作

#### 备份数据库

:::warning
为避免数据丢失，升级前请务必备份元数据库。请根据数据库类型选择合适的备份方式，例如 MySQL 使用 `mysqldump`，SQLite 直接复制数据库文件。
:::

### 升级数据库

V0.8.2 增量升级包含以下元数据变更：

| 变更 | 说明 |
| --- | --- |
| `dbgpt_session_file` | 存储归属于用户的会话与定时任务文件元数据，包括稳定的公开文件 ID、受管存储 URI、检查状态和任务文件来源关系。 |
| `code_graph_vertex`、`code_graph_edge`、`code_graph_meta` | 持久化 Code Graph 索引（AST 节点、结构关系和按知识空间的构建元数据），用于代码结构检索。 |
| `knowledge_space.index_methods` | 新增可空列，存储所选索引方式的 JSON 列表（例如 `["VectorStore", "FullText", "KnowledgeGraph"]`）。 |
| `gpts_messages.content` | 扩展为 `LONGTEXT`，避免较长的 Agent 消息和执行报告写入失败。 |

对 MySQL 元数据库执行增量脚本：

```bash
mysql -u <user> -p dbgpt < assets/schema/upgrade/v0_8_2/upgrade_to_v0.8.2.sql
```

### 安装依赖

请根据你的部署方式安装或更新依赖。如果使用源码方式和默认配置安装：

```bash
uv sync --all-packages
```

如需使用可选集成，请按需安装对应 Extra：

```bash
# Agentic 知识库检索和 RAG 依赖
uv sync --all-packages --extra "rag"

# Milvus 向量存储
uv sync --all-packages --extra "storage_milvus"
```

### 重启 DB-GPT

使用原有启动方式重启 DB-GPT 服务。启动后建议验证：

- 历史对话和知识空间可以正常加载。
- 可以在一个对话中上传、预览、移除和分析多个文件。
- 从含附件对话创建的定时任务可以访问冻结后的任务文件。
- Agentic 知识库检索可以使用已配置的索引方式完成检索，并展示来源引用。
- 并行子 Agent 任务和交互式问题可以在前端正确更新。

## 致谢

感谢所有为本版本作出贡献的开发者：@Aries-ckt, @Bartok9, @Carbene,  @Dellorchid, @DreamZhongJu, @Osamaali313, @XiaoHuo888-hue, @chen-alan, @chenliang15405, @chuenchen309, @mumubuku, @yyyCode

## 参考链接

- [DB-GPT V0.8.1 发版说明](http://docs.dbgpt.cn/docs/next/changelog/Released_V0.8.1)
- [快速开始](http://docs.dbgpt.cn/docs/overview/)
- [安装指南](http://docs.dbgpt.cn/docs/next/installation/)
- [RAG 基础概念](http://docs.dbgpt.cn/docs/next/getting-started/concepts/rag)
- [知识库索引设计原则](http://docs.dbgpt.cn/docs/next/design/kb_index_principles)
