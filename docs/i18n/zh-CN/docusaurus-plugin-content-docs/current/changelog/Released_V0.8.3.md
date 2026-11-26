# 🚀 DB-GPT V0.8.3 — 从分析到可信交付：可追溯报告、数据看板与 Agent 可观测性

V0.8.2 完善了多文件输入、知识检索、并行子 Agent 和人在回路，让复杂数据任务能够端到端执行。V0.8.3 进一步关注执行之后的结果如何核验、沉淀和持续使用：报告中的指标、图表和结论需要能够回到真实的 SQL、Python 与知识来源；一次分析形成的看板需要能够编辑、保存和发布；Agent 的模型调用、工具执行、Token 消耗与延迟也需要清晰可查。

围绕这些目标，本版本推出**结构化可追溯分析报告**与 **Dashboard 工作区**，新增 **Agent 可观测性**、**LLM-Wiki**、**模型提供商配置界面**和**可配置 Sandbox 运行时**，并扩展搜索、模型与向量存储生态，让 AI 数据助理从“完成分析”进一步走向“交付可复核、可维护的数据产品”。

### 关键特性速览

- 📊 **结构化可追溯分析报告** — 将报告内容与真实执行产物关联，支持来源详情、证据图谱、版本保存及 HTML/PDF 导出
- 📈 **Dashboard 工作区** — 将自然语言分析转化为可校验、可编辑、可保存、可发布和可分享的数据看板
- 🔭 **Agent 可观测性** — 在一个界面中查看 Agent 执行链、模型用量、Token 成本、P95 延迟与错误率
- 📚 **LLM-Wiki 与外部知识来源** — 自动构建可持续更新的知识页面和链接图谱，并新增飞书、语雀知识来源
- ⚙️ **可配置 Sandbox 运行时** — 支持 Local、Docker、Podman 和 Nerdctl，明确执行边界，不在容器失败时静默回退到宿主机
- 🧩 **模型、搜索与存储生态扩展** — 新增模型提供商配置 UI、Synthorai、Serply、Keenable Search 和 Qdrant 元数据索引
- 🛡️ **安全与稳定性加固** — 收紧文件访问、知识空间和连接器接口边界，修复路径穿越、SQL 注入及多项报告与看板稳定性问题

## 核心特性

### 📊 可追溯分析报告：让每个重要结论都有据可查

数据分析报告的交付不能只停留在一段文字或几张图表。业务人员还需要知道：某个指标来自哪次查询，图表使用了哪些字段，计算依赖哪些输入文件，引用的业务口径来自哪篇文档。V0.8.3 新增结构化、可追溯的数据分析报告，将报告内容与任务执行过程中产生的真实结果关联起来。

- **捕获真实执行产物**：记录 SQL 查询、Python 分析、知识库检索、文件读取和 Skill 执行产生的结果，而不是只保留模型生成后的文字。
- **绑定报告证据**：通过稳定的产物 ID、字段路径和内容选择器，将指标、图表、表格和正文内容关联到对应来源。
- **查看上下游依赖**：在来源详情和证据图谱中检查 SQL、代码、结果摘要、知识引用、输入文件及输出文件之间的关系。
- **保存不可变运行快照**：持久化报告、报告版本、执行产物、依赖关系和证据引用，重新打开后仍可复核。
- **改进校验与恢复**：通过会话证据目录提供已知指标、字段路径和业务含义；对已保存的命名占位符模板优先进行程序化重渲染，减少不必要的模型修复调用。
- **支持报告交付**：完善报告工作区、图表渲染以及 HTML/PDF 导出流程。

证据校验覆盖来源身份、字段路径、数值和图表绑定。对于能够与已捕获结果唯一对应的数据，系统可以程序化建立引用；来源无法确定或数值不一致时，仍会保留校验，避免将不确定内容静默渲染为可信结果。

<img alt="选择数据后执行分析并生成可追溯经营报告" src="/img/traceable-report/zh-CN/figure-04.png" width="720px" />

<img alt="中文界面中的 Olist 电商经营分析与可追溯报告生成过程" src="/img/traceable-report/zh-CN/figure-05.png" width="720px" />

<img alt="中文界面中的 Olist 电商经营分析与可追溯报告生成过程" src="/img/traceable-report/zh-CN/figure-06.jpeg" width="720px" />

<img alt="中文界面中的 Olist 电商经营分析与可追溯报告生成过程" src="/img/traceable-report/zh-CN/figure-07.png" width="720px" />

<img alt="中文界面中的 Olist 电商经营分析与可追溯报告生成过程" src="/img/traceable-report/zh-CN/figure-08.png" width="720px" />


> 证据绑定用于说明报告内容的来源，不代表系统已经自动验证全部自然语言结论的正确性。业务口径、分析假设和建议仍需结合实际场景复核。

首页同步新增 **Olist 巴西电商经营诊断**示例，将数据源、指标治理文档、知识索引和报告生成串成完整流程。内置数据库使用合成演示数据，并非真实 Olist 交易数据；如需基于真实数据分析，可按示例说明单独下载并导入。

<img alt="中文界面中的 Olist 电商经营分析与可追溯报告生成过程" src="/img/traceable-report/zh-CN/olist-analysis.png" width="720px" />

<img alt="通过证据图谱查看来源、执行过程与输出文件的完整链路" src="/img/traceable-report/zh-CN/figure-10.png" width="720px" />

### 📈 Dashboard 工作区：把一次分析沉淀为可持续使用的数据产品

V0.8.3 新增 Dashboard 工作区，将自然语言需求、数据探索、看板规划、草稿编辑和发布分享连接为一条完整链路。Agent 负责探索数据和提出规划，服务端负责授权、校验、查询执行与持久化，用户则在浏览器中审阅和修改，而不是直接接受一个无法检查的黑盒结果。

#### 从自然语言创建到持续维护

- **先规划，再创建**：选择有权限的数据源或关联文件，由 Agent 探索表、字段与样本，用户确认指标、维度、筛选和组件规划后生成草稿。
- **服务端校验**：对 Schema、跨字段引用、只读 SQL、表字段允许列表、查询参数和真实查询结果进行检查。
- **可编辑工作区**：支持 KPI、折线图、柱状图、饼图和表格等组件，并提供日期、单选、多选、文本和数字范围筛选。
- **AI 批注与变更审阅**：通过自然语言批注提出修改，先查看变更提案，再决定是否应用；解释和异常分析不会静默修改草稿。
- **草稿与修订管理**：保存时检查预期修订号，检测并发冲突，避免后提交的修改覆盖他人已经保存或发布的内容。

<img alt="中文界面中的 Dashboard 规划确认与查询生成过程" src="/img/dashboard/zh-CN/img.png" width="720px" />

<img alt="中文界面中的 Apple 财务 Dashboard 可编辑工作区" src="/img/dashboard/zh-CN/img_1.png" width="720px" />

<img alt="中文界面中的 Dashboard AI 批注与变更提案审阅" src="/img/dashboard/zh-CN/img_2.png" width="720px" />

#### 发布、分享与访问边界

Dashboard 区分 **Schema**（查询与展示定义）和 **Snapshot**（某次执行结果）。固定历史发布会冻结当次 Schema 与数据；持续分享则按已发布定义重新物化数据，并受有效期、撤销和数据源权限约束。编辑草稿不会自动替换已发布内容。

公开访客只能查看和使用允许的筛选，不能提交任意 SQL、替换数据源或修改草稿。看板编辑权限也不等于底层数据源权限，主数据源及联合查询引用的所有数据源都需要通过服务端授权检查。

<img alt="中文界面中的 Dashboard 发布方式选择" src="/img/dashboard/zh-CN/dashboard-publish-mode.png" width="720px" />

<img alt="英文界面中已发布的 Apple 财务 Dashboard 只读快照" src="/img/dashboard/en/apple-dashboard-published.png" width="720px" />

<img alt="基于合成零售数据创建并发布的 Dashboard 工作区" src="/img/dashboard/walmart-core-desktop-20260929.png" width="720px" />

### 🔭 Agent 可观测性：看清每一次模型与工具调用

复杂 Agent 任务出现问题时，只看最终回答往往无法定位原因。V0.8.3 新增内置可观测性能力，将 Agent 轮次、LLM 调用和工具执行记录为可关联的 Span，并通过 `trace_id` 与对话消息连接，无需切换到外部链路追踪系统。

- **总览看板**：提供最近 24 小时的 Agent 数量、事件数、Token 总量、P95 延迟和错误率，并按模型汇总调用次数、输入/输出 Token 与平均延迟。
- **链路列表与详情**：按一次 Agent 执行查看完整 Trace，通过可折叠 Span 树检查 Agent、模型、成本、耗时、状态和原始元数据。
- **对话内 Trace**：将当前对话还原为“用户问题 → 系统提示词 → 思考 → 工具调用与返回 → 回复”的消息流时间线。
- **开箱即用**：默认使用独立的 SQLite 文件 `logs/observability.db`，不让高吞吐遥测数据占用主业务数据库；读侧通过可插拔 Provider 协议扩展其他后端。

<img alt="英文界面中的 Agent 可观测性总览、Token 用量、延迟与 Agent 健康状态" src="/images/observability/en/overview.png" width="720px" />

<img alt="英文界面中的对话 Trace 消息流时间线" src="/images/observability/en/conversation-trace.png" width="720px" />

<img alt="英文界面中的对话 Trace 工具调用与执行细节" src="/images/observability/en/conversation-trace-tools.png" width="720px" />

### 📚 LLM-Wiki：让知识空间持续生长为可维护的知识网络

传统知识库以文档和 Chunk 为主要组织方式，适合检索片段，却不一定便于理解实体、概念和跨文档关系。V0.8.3 新增 **LLM-Wiki 索引**，由 Agent 阅读知识空间中的文档，自动生成互相链接的 Markdown 页面，包括实体、概念、逐文档摘要和目录页，并构建可视化链接图谱。

- **增量更新**：新文档到达或内容变化后，重新生成受影响的 Wiki 页面，而不必每次重建整个知识空间。
- **多种浏览方式**：通过目录树、页面阅读器和 Wiki 图谱查看知识结构与页面关系。
- **编辑与版本历史**：生成的知识页面可以继续维护，并保留版本记录。
- **Agent 可直接使用**：绑定已开启 Wiki 的知识空间后，Agent 自动获得 `kb_wiki_*` 只读工具；普通知识检索也会利用 Wiki 内容。

<img alt="LLM-Wiki 页签与自动生成的知识目录" src="/images/web-ui/llm-wiki/08-wiki-tab.png" width="720px" />

<img alt="LLM-Wiki 页面链接图谱" src="/images/web-ui/llm-wiki/12-wiki-graph.png" width="720px" />

<img alt="英文界面中的 LLM-Wiki 索引方式与生成配置" src="/images/web-ui/llm-wiki-en/13-wiki-index-config.png" width="720px" />

<img alt="英文界面中的 LLM-Wiki 中文文档目录与知识页面" src="/images/web-ui/llm-wiki-en/14-wiki-document-tree.png" width="720px" />

知识来源同步扩展至**飞书**和**语雀**。外部文档进入统一知识管线后，可以继续执行分块、检索和 LLM-Wiki 增量更新，无需为不同平台单独维护一套入库流程。

### 🧩 模型提供商配置：从编辑配置文件到可视化管理

V0.8.3 新增**模型提供商配置**页面，支持在 UI 中完成提供商接入与模型管理，减少手工修改 TOML 和重启服务的操作。

- 按 `llm`、`text2vec` 和 `reranker` 三类 Worker 管理模型。
- 凭证按提供商保存，每个模型可以独立启用或停用；启用后启动对应 Worker，停用后释放并发槽位。
- 连接内置提供商时进行真实凭证或连通性校验，已连接的提供商与启用的模型在服务重启后自动恢复。
- 支持添加任意 **OpenAI 兼容**端点，接入 vLLM、LiteLLM 网关、one-api、FastChat、Xinference 或企业内部网关。
- 新增 **Synthorai** 代理 Provider，通过一个 OpenAI 兼容端点和密钥访问其模型目录；未列入内置元数据目录的模型仍可按照实际模型 ID 路由。

<img alt="英文界面中的模型提供商目录、连接状态与模型启停管理" src="/images/model-providers-ui/en/providers-overview.png" width="720px" />

### ⚙️ 可配置 Sandbox 运行时：明确代码在哪里执行

V0.8.3 将应用侧 Python 和 Shell Agent 工具接入统一的运行时选择机制，主 Agent 与子 Agent 共用相同执行入口。用户可以通过 `SANDBOX_RUNTIME` 显式选择 `local`、`docker`、`podman` 或 `nerdctl`。

| 运行时 | 行为与边界 |
| --- | --- |
| `LocalRuntime` | 默认运行时，使用 DB-GPT 当前 Python 环境并在服务所在主机执行 Shell；不需要容器镜像，但不提供容器隔离 |
| `DockerRuntime` | 使用可连接的 Docker daemon 和 `SANDBOX_AGENT_IMAGE` 指定镜像执行 |
| `PodmanRuntime` | 使用可用的 Podman 后端执行 |
| `NerdctlRuntime` | 使用可用的 Nerdctl 后端执行 |

即使机器已经安装 Docker，DB-GPT 也不会自动启用容器。显式选择容器运行时后，如果镜像拉取、会话初始化或输入文件传输失败，工具会直接返回错误，**不会在宿主机上静默执行代码**；代码开始执行后的错误、超时或取消也不会切换到其他运行时重跑。

容器模式采用短生命周期执行会话：按需传入工作目录和显式输入文件，执行结束后回收普通文件与产物并清理容器。需要长期保留的依赖应预装到 Agent 镜像中。

### 🔎 搜索与存储生态扩展

- **Serply 搜索工具**：新增 `serply_search`，通过 Serply API 获取 Google 搜索结果；配置 `SERPLY_API_KEY` 后即可作为 Agent 搜索资源使用。
- **Keenable Search MCP 连接器模板**：内置 Streamable HTTP 接入方式，提供 `search_web_pages` 和 `fetch_page_content` 两个只读工具；无需 API Key 即可使用公共额度，也可配置 Bearer Key 提升限额。
- **Qdrant 可配置元数据 Payload 索引**：通过 `metadata_indexes` / `QDRANT_METADATA_INDEXES` 为 `session_id`、页码等过滤字段建立索引，支持 `keyword`、`integer`、`float`、`bool`、`datetime` 和 `uuid` 类型；默认为空，不改变既有部署行为。
- **Valkey 客户端识别**：通过 `lib-name` 客户端信息标记 Valkey 连接，便于在监控工具中识别 DB-GPT 客户端。

在 PR 提供的 Qdrant 1.20.0、20 万 Chunk、按 `session_id` 过滤的验证场景中，单次查询由约 **138 ms 降至 1.4 ms**，且结果与精确搜索一致。实际收益取决于集合规模、数据分布和过滤条件。

### 🛡️ 安全与稳定性加固

V0.8.3 继续收紧 Agent、知识库、连接器和文件系统的安全边界：

- 将 `get_file` 限制在会话工作目录，将 Agent 文件下载限制在 Agent 输出目录，并将 `FileClient` 的读取和删除限制在上传目录。
- 修复 Flow ZIP 导入文件名、知识空间删除接口中的路径穿越风险，以及连接配置 DAO 中的 SQL 注入风险。
- 修复知识空间作用域与 Benchmark 安全问题，加强 Skill 上传和 Dashboard 模板创建校验。
- 连接器确认接口要求 API Key，避免未授权执行确认操作。
- 图配置缺失时明确拒绝请求，避免使用不完整配置继续执行。
- Agentic 流程默认完成预算提升至 16384 Tokens，并接通 UI、环境变量和 TOML 配置；Dashboard 默认生成超时由 180 秒提升至 600 秒，减少复杂看板规划在确认阶段被截断的问题。
- Excel 知识加载读取公式计算结果，而不是把公式文本当作单元格值。
- 修复流式调用中 `BaseOutputParser` 未返回文本、容器时区配置、Spark 表信息查询和新建任务会话状态等问题。

## 功能增强

- 改进报告证据核查、证据目录、图表绑定和报告恢复流程（[#3348](https://github.com/eosphoros-ai/DB-GPT/pull/3348)）
- 新增 Qdrant 可配置元数据 Payload 索引（[#3305](https://github.com/eosphoros-ai/DB-GPT/pull/3305)）
- 新增结构化、可追溯的数据分析报告及报告工作区（[#3295](https://github.com/eosphoros-ai/DB-GPT/pull/3295)）
- 新增 Dashboard 工作区，并升级 Next.js 16 工具链（[#3278](https://github.com/eosphoros-ai/DB-GPT/pull/3278)）
- 新增 Keenable Search MCP 连接器模板（[#3227](https://github.com/eosphoros-ai/DB-GPT/pull/3227)）
- 使用 `lib-name` 客户端信息标记 Valkey 连接（[#3282](https://github.com/eosphoros-ai/DB-GPT/pull/3282)）
- 新增 LLM-Wiki 知识索引，并增加飞书、语雀知识来源（[#3276](https://github.com/eosphoros-ai/DB-GPT/pull/3276)）
- 新增可配置 Agent Sandbox 运行时（[#3272](https://github.com/eosphoros-ai/DB-GPT/pull/3272)）
- 新增 Serply 搜索工具（[#3243](https://github.com/eosphoros-ai/DB-GPT/pull/3243)）
- 新增模型提供商配置 UI（[#3241](https://github.com/eosphoros-ai/DB-GPT/pull/3241)）
- 新增 Synthorai 代理 LLM Provider（[#3210](https://github.com/eosphoros-ai/DB-GPT/pull/3210)）
- 新增 Agent 可观测性 Trace、总览看板与对话内 Trace 时间线（[#3212](https://github.com/eosphoros-ai/DB-GPT/pull/3212)）

## 问题修复

- 修复流式调用中 `BaseOutputParser` 未返回文本的问题（[#3363](https://github.com/eosphoros-ai/DB-GPT/pull/3363)）
- 将 `get_file` 的文件访问限制在会话工作目录内（[#3357](https://github.com/eosphoros-ai/DB-GPT/pull/3357)）
- 修复热门应用排序未使用分页偏移量的问题（[#3324](https://github.com/eosphoros-ai/DB-GPT/pull/3324)）
- 将 SQL 注释清理限定在 api-call 块的 `<sql>` 标签内，避免影响其他内容（[#3274](https://github.com/eosphoros-ai/DB-GPT/pull/3274)）
- 在图配置缺失时明确拒绝请求（[#3352](https://github.com/eosphoros-ai/DB-GPT/pull/3352)）
- 提高 Agentic 完成预算和 Dashboard 默认生成超时，并接通 UI、环境变量与 TOML 配置（[#3341](https://github.com/eosphoros-ai/DB-GPT/pull/3341)）
- 统一 Dashboard Builder Skill，并加强模板创建校验（[#3298](https://github.com/eosphoros-ai/DB-GPT/pull/3298)）
- 修复 Flow ZIP 导入、知识空间删除中的路径穿越风险，以及连接配置 DAO 的 SQL 注入风险（[#3339](https://github.com/eosphoros-ai/DB-GPT/pull/3339)）
- 在容器镜像中安装 `tzdata` 并支持配置容器时区（[#3219](https://github.com/eosphoros-ai/DB-GPT/pull/3219)）
- Markdown 标题切分器将不带语言标记的 `` ``` `` 代码围栏正确识别为代码块（[#3273](https://github.com/eosphoros-ai/DB-GPT/pull/3273)）
- 修复知识空间作用域隔离与 Benchmark 安全问题（[#3271](https://github.com/eosphoros-ai/DB-GPT/pull/3271)）
- 加强 Skill 上传安全校验（[#3270](https://github.com/eosphoros-ai/DB-GPT/pull/3270)）
- 补充 Skill 实现指南中缺失的导入（[#3226](https://github.com/eosphoros-ai/DB-GPT/pull/3226)）
- 连接器确认接口增加 API Key 校验（[#3264](https://github.com/eosphoros-ai/DB-GPT/pull/3264)）
- Excel 知识加载读取公式计算结果，而不是公式文本（[#3266](https://github.com/eosphoros-ai/DB-GPT/pull/3266)）
- 将 Agent 文件下载限制在 Agent 输出目录内（[#3257](https://github.com/eosphoros-ai/DB-GPT/pull/3257)）
- 移除 Tokenizer 错误信息中的重复单词（[#3246](https://github.com/eosphoros-ai/DB-GPT/pull/3246)）
- 修复 `double_click_open` 本地化文案乱码（[#3250](https://github.com/eosphoros-ai/DB-GPT/pull/3250)）
- 将 `FileClient` 的读取和删除操作限制在上传目录内（[#3237](https://github.com/eosphoros-ai/DB-GPT/pull/3237)）
- 补充缺失的 `agent_errors` 模块及相关测试（[#3224](https://github.com/eosphoros-ai/DB-GPT/pull/3224)）
- Flow 兼容迁移函数补充返回视图元数据（[#3221](https://github.com/eosphoros-ai/DB-GPT/pull/3221)）
- Worker 配置处理器补充返回配置字典（[#3220](https://github.com/eosphoros-ai/DB-GPT/pull/3220)）
- 修复 `SparkConnector.table_simple_info` 调用时触发 `TypeError` 的问题（[#3213](https://github.com/eosphoros-ai/DB-GPT/pull/3213)）
- 避免为 SQLite 创建空的父目录（[#3218](https://github.com/eosphoros-ai/DB-GPT/pull/3218)）
- 修复 `retriever_evaluation_example.py` 运行时触发 `TypeError` 的问题（[#3216](https://github.com/eosphoros-ai/DB-GPT/pull/3216)）
- 新建任务时重置会话状态，避免沿用上一任务上下文（[#3214](https://github.com/eosphoros-ai/DB-GPT/pull/3214)）
- 将 `LOCAL_DB_SSL_VERIFY` 正确解析为布尔值（[#3211](https://github.com/eosphoros-ai/DB-GPT/pull/3211)）

## 文档与其他改进

- 修正快速开始、安装、AWEL 和模块文档中的拼写问题（[#3286](https://github.com/eosphoros-ai/DB-GPT/pull/3286)）
- 修正 Excel 知识、评估模块、`add_command` 和 `ReduceStreamOperator` 等文档字符串中的参数说明（[#3248](https://github.com/eosphoros-ai/DB-GPT/pull/3248)）（[#3253](https://github.com/eosphoros-ai/DB-GPT/pull/3253)）（[#3252](https://github.com/eosphoros-ai/DB-GPT/pull/3252)）（[#3260](https://github.com/eosphoros-ai/DB-GPT/pull/3260)）（[#3261](https://github.com/eosphoros-ai/DB-GPT/pull/3261)）
- 修正过期的 `community_summary` 导入路径（[#3254](https://github.com/eosphoros-ai/DB-GPT/pull/3254)）
- 使 stale-bot 提示信息与配置的超时时间保持一致（[#3251](https://github.com/eosphoros-ai/DB-GPT/pull/3251)）
- 更新 Web 构建文件（[#3230](https://github.com/eosphoros-ai/DB-GPT/pull/3230)）

## 升级指南

本指南适用于从 **v0.8.2** 升级到 **v0.8.3**。更早版本请先按照历史升级文档依次升级到 v0.8.2。

V0.8.3 的增量元数据脚本新增 **19 张表**，并为 **3 张存量表增加 10 个字段及相关索引**，用于 Dashboard、可追溯报告、定时任务资源关联与执行租约、运行幂等和消息追踪。升级脚本位于 `assets/schema/upgrade/v0_8_3/` 目录：

- `upgrade_to_v0.8.3.sql`：在 v0.8.2 数据库基础上执行的增量脚本。
- `v0.8.3.sql`：用于全新安装的完整 v0.8.3 Schema；全新环境执行全量脚本后，无需再执行增量脚本。

> 与历史版本一致，增量脚本面向 MySQL。SQLite 用户请在升级前备份元数据库，由 ORM 管理的表和字段通过服务启动时的建表与迁移入口处理。可观测性数据默认写入独立的 `logs/observability.db`，不写入主业务数据库。

### 准备工作

#### 备份数据库

:::warning
为避免数据丢失，升级前请务必备份元数据库。请根据数据库类型选择合适的备份方式，例如 MySQL 使用 `mysqldump`，SQLite 直接复制数据库文件。
:::

#### 确认前端构建环境

如果从源码构建前端，建议使用 **Node.js 20.19**。Next.js 16 要求 Node.js **>= 20.9.0**，本版本前端构建基线为 Node.js 20.19，并统一使用 Webpack。

### 升级数据库

**已有 MySQL 部署必须在启动新版前完成增量升级。** 漏跑脚本会导致定时任务缺少 `owner_id`、`resource_*`、`lease_*` 等字段及运行记录幂等索引，可能出现 `Unknown column` 等错误，并影响存量定时任务和 Dashboard 功能。

V0.8.3 增量升级包含以下元数据变更：

| 变更 | 说明 |
| --- | --- |
| `dbgpt_serve_scheduled_task` | 新增 `owner_id`、`resource_type`、`resource_id`、`lease_owner`、`lease_expires_at`，用于稳定授权身份、资源关联、执行互斥与续租。 |
| `dbgpt_serve_scheduled_run` | 新增 `output_resource_id`、`attempt_count`、`result_json`、`idempotency_key`，并增加 `(task_id, idempotency_key)` 唯一索引，记录结果资源、重试与结构化结果，防止重复执行。 |
| `chat_history_message` | 新增 `trace_id` 及索引，将聊天消息与 Agent 执行链路关联。 |
| Dashboard 与上传数据集相关的 14 张表 | 保存看板草稿、编辑修订、AI 批注、操作记录、发布快照、持续分享、成员权限、审计、封面和上传数据集等信息。 |
| 可追溯报告相关的 5 张表 | 保存报告身份、不可变运行快照、执行产物、产物依赖关系和报告证据绑定。 |

对 MySQL 元数据库执行增量脚本：

```bash
mysql -u <user> -p dbgpt < assets/schema/upgrade/v0_8_3/upgrade_to_v0.8.3.sql
```

如果元数据库名称不是 `dbgpt`，请先调整脚本中的 `USE dbgpt;` 和连接命令。脚本对存量表使用直接的 `ALTER TABLE ... ADD COLUMN` / `ADD INDEX`，**只应执行一次**；如果此前已经运行过旧版 Dashboard SQL 或手工执行过部分 DDL，请先核对已有字段和索引，只执行缺失项，不要重复执行整份增量脚本。

### 安装依赖

请根据部署方式安装或更新 Python 依赖。如果使用源码方式和默认配置安装：

```bash
uv sync --all-packages
```

如需使用 Qdrant 向量存储及元数据 Payload 索引，请安装对应 Extra：

```bash
uv sync --all-packages --extra "storage_qdrant"
```

从源码构建前端时，重新安装依赖并执行生产构建：

```bash
cd web
yarn install
yarn build
```

### 按需调整运行配置

LocalRuntime 仍是默认 Sandbox 运行时。只有需要容器隔离时才显式选择容器后端，并提前准备可用的 daemon 与 Agent 镜像：

```bash
export SANDBOX_RUNTIME=docker
export SANDBOX_AGENT_IMAGE=dbgpt-sandbox-agent:latest
```

如需为 Qdrant 的元数据过滤字段建立 Payload 索引，可按需配置；未设置时默认不创建额外索引：

```bash
export QDRANT_METADATA_INDEXES="session_id,page:integer"
```

## 致谢

V0.8.3 的发布离不开社区开发者的持续贡献。

### 🎉 新贡献者
V0.8.3 版本新增 22 位 新的贡献者：
- @Anai-Guo
- @yetuge
- @AvAl4nch
- @Goodnight77
- @Jonathan-Improving
- @L4XB
- @LostSnowfluff
- @MindOfqc
- @MohammadHijjawi97
- @bosprimigenious
- @cuihuan
- @drakeo338
- @gaurav0107
- @googio
- @ilya-bogin-keenable
- @jcsdxhe
- @simpleqt
- @someorz
- @toyeshhm
- @ump45nose
- @xiaoyvhuv
- @yetuge

🔥🔥 感谢所有贡献者使这次发布成为可能！
@Anai-Guo, @Aries-ckt, @AvAl4nch, @Goodnight77, @Jonathan-Improving, @L4XB, @LostSnowfluff, @MindOfqc, @MohammadHijjawi97, @bosprimigenious, @chen-alan, @chenliang15405, @cuihuan, @drakeo338, @gaurav0107, @googio, @ilya-bogin-keenable, @jcsdxhe, @simpleqt, @someorz, @toyeshhm, @ump45nose, @xiaoyvhuv and @yetuge

## 参考链接

- [DB-GPT V0.8.2 发版说明](http://docs.dbgpt.cn/zh-CN/docs/next/changelog/Released_V0.8.2)
- [快速开始](http://docs.dbgpt.cn/zh-CN/docs/overview/)
- [安装指南](http://docs.dbgpt.cn/zh-CN/docs/next/installation/)
- [可追溯分析报告设计](http://docs.dbgpt.cn/zh-CN/docs/next/design/traceable_analysis_report)
- [Dashboard 工作区设计](http://docs.dbgpt.cn/zh-CN/docs/next/design/dashboard)
- [Agent 可观测性](http://docs.dbgpt.cn/zh-CN/docs/next/modules/observability)
- [LLM-Wiki](http://docs.dbgpt.cn/zh-CN/docs/next/getting-started/web-ui/llm-wiki)
- [模型提供商配置](http://docs.dbgpt.cn/zh-CN/docs/next/getting-started/model-providers-ui)
- [Sandbox 运行时配置](http://docs.dbgpt.cn/zh-CN/docs/next/sandbox/runtime)

