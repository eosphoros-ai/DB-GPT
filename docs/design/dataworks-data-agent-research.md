# 阿里 DataWorks Data Agent 能力调研 & DB-GPT 集成映射

> 调研日期：2026-10-20 ｜ 面向：DB-GPT 企业数据 Agent 产品规划
> 结论先行：阿里把"数据智能体"拆成 **Agent 智能体 / 代码编程助手 / ChatBI / 快捷 AI 操作** 四大块，全链路覆盖集成-开发-运维-治理-分析。对 DB-GPT（定位"业务库智能取数+分析"）最值得对标、也最缺的是 **YAML 语义模型层** 和 **ChatBI 式问数-报告闭环**；而你已经在做的 **工具审批** 恰好对上了新版 Data Agent 的"审批模式"。

---

## 一、产品定位与演进

**Data Agent** 是 DataWorks 平台内置的一站式 AI 智能体（不是独立产品，深度嵌入 DataWorks 各模块），主张"说需求，得成果 / 需求即代码"，用自然语言贯通 **数据集成 → 开发 → 运维 → 治理 → 分析** 全生命周期。

演进上分两条腿（官方明确）：

- **智能 SQL 编程助手**：辅助 SQL 编程，NL2SQL + 代码补全（早期主打，2024 起邀测）。
- **AI Agent + LUI**：自然语言用户界面，自主规划 + 调工具执行复杂任务（当前主打）。

形态上也分两代：

| 代际 | 载体 | 特点 |
|---|---|---|
| 原版 Agent 智能体 | Data Studio 侧边栏对话面板 | 轻量问答 + 5 类专用 Agent，`/` 唤起 |
| **新版 Data Agent** | 独立全页面，**基于 Qwen Code** | 更强推理规划 + Coding，内置 Skills，**审批模式**，多模型切换 |

> 关键情报：新版 Data Agent 基于 **Qwen Code** 构建——即阿里把 CLI Coding Agent 那套（Skills、审批模式、MCP 工具、待办清单）搬进了数据平台。这与你 DB-GPT 里 **pi 引擎（Qwen Code 系）+ tool-approval + skills** 的技术选型高度同源，集成范式可直接借鉴。

商业化：自 **2026-04-15** 起 Data Agent / ChatBI 正式收费（Token 费 + Serverless 资源组费，1 实例占 1 CU，1 小时不用自动停机）。

---

## 二、产品能力全景（四大核心 + DI 垂直集）

### 2.1 Agent 智能体（自动化完成复杂任务）

机制：LLM 深度思考 + 任务分解 + 制定执行计划 → **调用 MCP Server 工具集** 自动执行。5 类专用 Agent，`/` 选择（在对应模块下自动匹配，无需手动选）：

| Agent | 能力 |
|---|---|
| **数据集成 Agent** | 自然语言描述同步需求 → 自动解析语义、生成同步任务配置（源/目标类型、表结构映射、字段过滤、分区策略、调度参数） |
| **数据开发 Agent** | NL 驱动 ETL 全流程：需求分析 → 代码生成 → 工作流生成 → 发起发布 |
| **数据运维 Agent** | 任务实例健康评估：融合依赖链路/资源水位/历史趋势/变更影响/日志异常/数据质量 → 结构化诊断报告 |
| **数据地图 Agent** | 自然语言找表（"找和用户活跃度相关的汇总表"）、指定范围检索、深度追问血缘/负责人/字段释义 |
| **数据治理 Agent** | "自主式治理"：NL 指令 → 精准治理动作（自动配质量规则、治理已发现的质量问题） |

配套机制：
- **上下文引用**：`@` 添加 表 / 节点代码文件 / 数据专辑 / Rules / 本地文件。
- **智能模型调度（Auto 模式）**：按子任务自动分配最优模型，单次对话内多模型动态协同。
- **过程可视化**：待办事项清单（子步骤状态自动更新）+ 执行总结报告 + 任务耗时 + Token 消耗统计。

### 2.2 代码编程助手（NL2SQL / SQL 补全）

官方列出的 NL2SQL **8 大适用场景**：① 简单数据查询（取数）② SQL 优化与转换（SQL→SQL，如列转行）③ SQL 语法查询与讲解 ④ 函数查询 ⑤ 功能咨询（不知用啥语法时给建议+示例）⑥ 注释生成（批量给 DDL 字段生成 Comment）⑦ SQL 解释（复杂 SQL 拆解逐段讲解）⑧ SQL 一键纠错。

代码补全能力：SQL/Python 的 生成/问答/改写/优化/纠错/注释/测试用例生成/解释；编辑器内 **Tab 采纳补全**；右键菜单 Copilot 快捷操作；多模型切换（默认模型、Qwen3-235B-A22B 等）；**上下文感知**（对话内容、代码、表结构、数据血缘、自定义知识库）。

官方点明 SQL 补全比 Java/Python 难的 7 个原因（元数据依赖、语义多样性、方言差异、执行计划、业务口径相关性、公开数据集少…）——本质都在强调 **元数据 + 业务知识上下文** 的重要性，这也是语义层的价值锚点。

### 2.3 ChatBI（对话式智能分析 / 智能问数）

定位：扮演"专业数据分析师"，基于**目标数据集**提问，全流程自动化：**问题理解 → 目标表识别 → 查询代码生成及运行 → 绘制可视化图表 → 结论提炼**，产出图文并茂的分析报告。

使用流程：
1. **创建数据集**（圈定分析范围：数据源中的表 或 本地文件）——这是 ChatBI 的核心前置，先框定"在哪些数据上问"。
2. 新建会话提问，自动完成上述链路，结果自动匹配图表（折线/柱状/饼图）。
3. （可选）**创建知识库**：配置 **问题模板、术语词条、业务逻辑**，纠偏模型理解，提升 SQL 准确率。
4. （可选）**报告分享**：生成 HTML 链接 或 导出 PDF。

### 2.4 快捷 AI 操作（模块内嵌 Copilot 按钮）

| 操作 | 场景 |
|---|---|
| 查询结果智能可视化 | 一键把查询结果生成图表 + 数据见解 |
| AI 智能建表 | 输入表名关键字 → 自动生成字段定义 + DDL，智能补全字段名/描述 |
| 任务发布描述生成 | 发布环节一键生成上线描述 |
| 任务异常智能诊断 | 运维中心秒级提取日志关键信息 + 错误分析 + 修复建议（对接 Qwen、DeepSeek-R1） |
| 数据质量规则智能推荐 | 基于元数据一键生成质量规则 |
| 数据服务 API 生成 | 一键生成 SQL 脚本并自动解析为 API 请求/返回参数 |

### 2.5 DI Agent（数据集成垂直能力集，六大能力）

对话式任务配置（单表离线/实时、整库离线/实时统一管理）、**AI 数据处理（多模态 ETL，把大模型当 ETL 算子嵌入 Source→Transform→Sink 流水线，支持图片/视频/音频/文档识别打标转写翻译摘要向量化）**、**ChatDB 数据问答与管理**（复用 80+ 数据源连接器，业务语言即问即答 + 建库建表 + 表结构变更 + 库表结构诊断 + 慢 SQL 性能排查）、AI 诊断、智能周期巡检（Cron 主动扫描出报告）、智能运维值守、**IM 频道集成**（钉钉/微信/飞书直接操作）。

---

## 三、技术架构与实现要点

### 3.1 语义层：YAML 语义模型（**本次调研最有价值的部分**）

Data Agent 提供独立的 **"语义分析"** 功能：自动扫描数据源（当前仅 MaxCompute），提取表间关联/字段语义/指标口径，生成 **结构化 YAML 语义模型**，通过 `/dataworks-semantic` 指令注入会话上下文，显著提升问数与 SQL 生成准确率。

**生成方式（双维度交叉验证）**：
- 维度一：读取"代码所在空间"的 SQL 脚本 + 调度任务，按业务域描述经 DataWorks 文件夹结构定位相关代码，**从真实 SQL 里提取指标计算口径**（如发现 `gmv = SUM(CASE WHEN order_status='paid' THEN pay_amount END)`）。
- 维度二：扫描重点分析表的元数据（字段含义、同义词、层级关系、指标定义、派生公式、示例问答）。
- 官方强调："选对代码空间"是质量分水岭——否则只能靠字段注释猜口径。

**YAML 顶层四大模块**：

| 模块 | 内容 |
|---|---|
| `ai_context` | `instructions`（业务域描述、数据分层 ODS→DWD→DWS→ADS、分区字段等全局信息）+ `few_shots`（真实"问题+SQL"示例） |
| `metrics` | 指标定义：`name` / `description` / `synonyms`（同义词，如 GMV=成交额/销售额/交易额）/ `expression`（含 `dialects` 多方言，如 MaxCompute: `SUM(gmv)`） |
| `metric_formulas` | 派生指标公式：如 `客单价 = GMV / 订单数` |
| `datasets` | 数据集定义：每张表的 source / description / 字段（name、type、含义、synonyms、`metric: true` 标记） |

**产品化形态**：图谱 + YAML 源码 **双屏联动**（点节点/边高亮源码行，移光标高亮图谱），在线编辑保存即时生效、支持对比修改/重置/回滚快照。

**`/dataworks-semantic` 是个内置 Skill**，提供语义模型全生命周期管理命令：`check / create / list / runs / download / sync / index / search / inspect / rollback / report / log`。典型流程：`check → list → download/sync → index → search → 加载 YAML 至会话上下文 → 精准问数`。产物缓存在本地 `.semantic/` 目录。加载仅对当前会话生效，可加载多个语义模型（多业务域并存）。

> 官方给的对照实验很有说服力：问"近 30 天各品类客单价"，**未加载语义模型**时 AI 把客单价误解为 `AVG(price)`、表名字段全猜错；**加载后**正确用 `SUM(gmv)/SUM(order_cnt)` + 正确表 + 正确统计周期。→ 印证"语义层 = 问数准确率的地基"。

### 3.2 审批 / 交互确认机制

新版 Data Agent 提供 **5 档审批模式**（对话输入框左下角切换）：

| 模式 | 行为 |
|---|---|
| `plan` 计划 | 仅分析，不改文件/不执行命令 |
| `default` 请求批准 | 编辑操作需确认后执行 |
| `auto-edit` 自动编辑 | 自动批准编辑，无需逐步确认 |
| `auto` 智能审批 | Agent 自主判断风险，仅高风险操作请求确认 |
| `yolo` 完全访问 | 自动执行所有工具/命令，无需确认 |

同时有 **8 类交互式确认触发点**：规划确认、破坏性操作（DROP/TRUNCATE/覆盖分区）、发布上线、信息补充（表名歧义/时间范围缺失）、高代价操作（全表扫描/大 JOIN，提示预估成本）、跨边界（跨项目/租户/环境）、权限变更（授权/共享/改 ACL）、长任务中断。

### 3.3 Skills / MCP / 模型

- **Skills 体系**：内置 DataWorks 官方 Skills（数据集成/开发/治理/安全 + ChatBI），按实例开关；支持上传**自定义 Skill**（名称+描述+Markdown 正文；或 zip 包，根目录放 `SKILL.md` 覆盖正文，其余作资源附件相对路径引用；SKILL.md ≤200KB，zip ≤50MB）；`/技能名` 显式调用，或按意图自动路由（如启用 ChatBI Skill 后，问数类提问自动路由）。
- **工具执行**：Agent 调用 **DataWorks MCP Server** 工具集，官方持续扩充。
- **模型**：qwen3.8-max / qwen3.7-max（默认）/ qwen3.7-plus / deepseek-v4-pro / glm-5.2；原版 Agent 支持 Auto 智能调度。

### 3.4 知识增强

- **Rules（自定义知识）**：企业级（管理员统一配，定生效范围，放公司级业务术语/编码规范）+ 个人级（个人偏好/常用片段），指导 Agent 思考回答。
- **Context**：每次对话 `@` 手动指定 表/节点代码/数据专辑/Rules/本地文件。
- **知识库（ChatBI）**：问题模板、术语词条、业务逻辑，纠偏问数。
- **经验沉淀**：AI 诊断结果自动归档为知识库条目，下次同类问题直接匹配。

### 3.5 引擎与数据源对接

计算引擎：MaxCompute / Hologres / AnalyticDB / StarRocks / EMR / CDH（湖仓一体）。ChatDB 复用数据集成 **80+ 数据源连接器**（MySQL/Oracle/Kafka/MaxCompute/Hologres/MongoDB/OSS 等），已接入数据源既是同步源/目标，也是可对话分析对象。语义分析当前仅支持 MaxCompute 数据源。

---

## 四、DB-GPT 能力映射与差距分析

> 映射基于当前仓库实盘（`packages/` + `web/`）。DB-GPT 定位是"业务库智能取数+分析"，**不做**数据集成 ETL / 调度运维 / 质量治理，故这几类 Agent 属"范围外差异"，非必须补齐。

| Data Agent 能力 | DB-GPT 现状（文件） | 差距 |
|---|---|---|
| **语义分析 / YAML 语义模型** | 仅 `DBSummary`（`rag/summary/db_summary.py`、`rdbms_db_summary.py`、`serve/datasource/service/db_summary_client.py`）做 schema 摘要注入；`schema_linking.py` 做表列裁剪；`indicator_assistant_agent.py` 指标能力很薄 | **🔴 最大差距**：无 metrics/metric_formulas/synonyms/few_shots 的结构化语义模型；无从 SQL 代码反提取口径；无语义图谱可视化编辑器；无 `/semantic` 式 skill 生命周期管理 |
| **ChatBI（数据集+问数+报告）** | `scene/chat_db/auto_execute`（NL→SQL→执行）、`scene/chat_dashboard`（图表）、`agent/expand/data_scientist_agent.py`、`actions/chart_action`/`dashboard_action` | **🟠 中差距**：有取数+出图零件，但缺"数据集圈定范围"、结论提炼报告、HTML/PDF 分享的产品化闭环封装 |
| **代码编程助手（NL2SQL 8 场景 + 补全）** | `chat_db`、`react_agent.py`、`chat_db/professional_qa`（只问答不执行） | **🟡 小差距**：生成/问答/解释具备；SQL 补全(Tab)、纠错、注释生成、测试用例、方言适配未产品化 |
| **Agent 智能体 + 多专用 Agent 路由** | `agent/core/base_agent.py`(ConversableAgent)、`agent/expand/*`、`core/awel`(DAG，chat_flow 节点=ToolCallingReActAgent) | **🟡 小差距**：多 Agent 与 DAG 编排在，但缺"`/` 选专用 Agent + 按场景自动路由"的 LUI 体验 |
| **审批模式（plan/default/auto-edit/auto/yolo）** | ✅ `openapi/api_v1/approval.py`（`ToolRiskPolicy` auto/confirm/deny 规则表 + `ApprovalCenter` 注册/等待/TTL 自动拒绝/作用域白名单 + `make_approval_gate` 注入 `tool_action`）、`web/new-components/chat/content/ApprovalDock.tsx` | **🟢 已对标**：规则分级已有；缺"会话级审批模式切换"和"auto 智能审批(Agent 自主判风险)" |
| **交互式确认触发点（破坏性/高代价/跨边界…）** | approval.py 高危工具含 shell/code/sql_query/web_fetch | **🟡**：已拦高危工具，但缺"高代价操作预估成本""跨边界/权限变更"等语义级触发点 |
| **Skills 体系（SKILL.md + zip + /命令）** | pi 引擎 `tool_bridge._skill_tools`（load_skill/get_skill_resource/execute_skill_script_file）、`web/pages/construct/skills` | **🟢 接近**：底座在（同为 Qwen Code 系）；缺自定义 Skill 上传 UI + `/命令` 路由 + 内置官方 Skill 库 |
| **上下文引用（@表/代码/文件/Rules）** | `QuestionDock.tsx`、chat 上下文；KB 检索 | **🟠**：@ 引用元数据/Rules 体系较弱 |
| **Rules（企业级/个人级知识）** | 无系统化 Rules，只有 KB | **🟠 中差距**：缺"规则/规范/口径"作为独立可配置知识源（呼应你"策略产品化进 setting 界面"的偏好） |
| **快捷 AI 操作（建表/诊断/质量/API）** | 零散，未产品化为模块内嵌 Copilot 按钮 | **🟡**：AI 建表、结果可视化可低成本补 |
| **数据集成/运维/治理 Agent、DI 多模态 ETL、IM 集成** | 无（范围外） | ⚪ 定位差异，非必须 |

---

## 五、集成建议（能力映射 → 落地优先级）

结合你既有资产（语义层设计定论：**结构化库=权威源，KB 托管空间=派生向量索引**；tool-approval P0；pi 引擎；chat_flow/AWEL），建议分三档：

### P0 —— 企业级语义层（最高价值，直击问数准确率）
在 DB-GPT 引入 **YAML 语义模型层**，作为 `DBSummary` 之上的权威语义源：
- 数据模型对齐阿里四模块：`ai_context(instructions+few_shots)` / `metrics(name/desc/synonyms/expression+dialects)` / `metric_formulas` / `datasets(fields+synonyms+metric标记)`。
- **发布链路复用你的既定方案**：语义模型存结构化库（权威源）→ 发布时写向量、chunk 带指针 metadata → 注入 `chat_db`/`react_agent` 的 prompt（`{table_info}` 处扩展为 `{semantic_model}`）。
- 生成方式借鉴阿里"双维度"：元数据扫描 + **从库内既有 SQL/视图反提取指标口径**（DB-GPT 面向业务库，可读 view 定义/存储过程/历史查询日志）。
- 与 `indicator_assistant_agent` 合流，把薄弱的指标能力升级为完整语义模型。

### P0 —— 审批模式产品化（低成本，已 80% 就位）
把 `approval.py` 的 auto/confirm/deny 规则表，包装成 **会话级审批模式切换**（plan/default/auto/yolo，UI 放 composer 左下角，对齐新版 Data Agent）；`ApprovalDock` 增"智能审批(auto)"档——由 Agent 自评风险分再决定是否弹确认。

### P1 —— ChatBI 式问数-报告闭环
把 `chat_db` + `chat_dashboard` + 报告产物（呼应你 `flow-output-artifacts` 多格式产物稿）封装成"**数据集 → 问数会话 → 结论提炼 → HTML/PDF 分享**"产品闭环；"数据集"= 圈定表范围 + 绑定语义模型。

### P1 —— Skills 产品化 + Rules 体系
- Skills：`web/pages/construct/skills` 补自定义 Skill 上传（SKILL.md + zip）、`/命令` 路由、内置官方 Skill 库（复用 pi `_skill_tools`）。
- Rules：新增"企业级/个人级规则"作为独立知识源，产品化进 setting 界面（多源配置 + UI 可定义 + 试运行框，符合你既定偏好），toml 仅作 bootstrap seed。

### P2 —— 体验增强
语义图谱可视化编辑器（图谱↔YAML 双屏联动）、`@` 上下文引用（表/代码/文件/Rules）、快捷 AI 操作（AI 建表、结果一键可视化）。

---

## 六、给 DB-GPT 的三条判断

1. **技术选型同源，范式可直搬**：阿里新版 Data Agent = Qwen Code + Skills + 审批模式 + MCP 工具，与你 pi 引擎那套几乎一致。Skills、审批模式、`/命令` 路由不是"要不要做"，而是"把已有底座产品化"。
2. **语义层是分水岭，也是你最大空白**：阿里用整块功能（语义分析 + YAML 模型 + 图谱编辑器 + `/semantic` skill）证明"问数准确率的地基是语义层"。这与你语义层设计定论完全一致，建议列为 P0，且数据模型直接对齐阿里四模块（少走弯路、便于对标）。
3. **范围要克制**：阿里是全链路数据平台（集成/开发/运维/治理/分析），DB-GPT 聚焦"业务库取数+分析"。数据集成 ETL、调度运维、质量治理属定位差异，不建议盲目补齐；把火力集中在 **语义层 + ChatBI 问数闭环 + 审批/Skills 产品化**。

---

### 参考来源
- Data Agent 概述：https://help.aliyun.com/zh/dataworks/user-guide/dataworks-copilot-intelligent-assistant-hands-on-practice
- 新版 Data Agent（Qwen Code / 审批模式 / Skills）：https://help.aliyun.com/zh/dataworks/user-guide/new-data-agent
- Agent 智能体（5 类专用 Agent / 上下文 / 模型调度）：https://help.aliyun.com/zh/dataworks/user-guide/dataworks-copilot-agent
- **Data Agent 语义分析（YAML 语义模型 / `/dataworks-semantic`）**：https://help.aliyun.com/zh/dataworks/user-guide/data-agent-semantic-analysis
- ChatBI 概述：https://help.aliyun.com/zh/dataworks/user-guide/dataworks-chatbi-overview
- 数据集成 DI Agent（六大能力 / ChatDB / 多模态 ETL）：http://intl.aliyun.com/help/zh/dataworks/user-guide/introduction-to-data-integration-and-ai-native-capabilities
- DataWorks Copilot NL2SQL / SQL 补全（8 场景）：https://developer.aliyun.com/article/1559452
