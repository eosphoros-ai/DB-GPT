# DB-GPT 任务流程（TaskFlow）产品化改造方案

> 废弃旧 AWEL Flow 编辑器的产品形态（节点即算子、参数即元数据），**保留 AWEL 引擎内核**；
> 以「连接数据库做数据分析」为第一场景重新包装：**粗粒度节点 + 内置模板 + 首页对话一键调用 + 对话内运行观测**。
>
> 设计稿：`docs/design/taskflow-mockups/`（HTML，首页 Manus 浅色风格，4 屏）
> 现状摸底：前端 `web/pages/construct/flow/*` + `web/components/flow/*`；后端 `packages/dbgpt-core/src/dbgpt/core/awel/` + `packages/dbgpt-serve/src/dbgpt_serve/flow/`

---

## 1. 背景与目标

### 1.1 现状问题

旧 Flow 编辑器（`/construct/flow/canvas`）本质是把 AWEL 引擎的算子注册表直接可视化：

- **节点即算子**：节点面板数据来自 `GET /api/v2/serve/awel/nodes`（`_OPERATOR_REGISTRY` 全量元数据），算子数百个，粒度是技术级的（`HKnowledgeOperator`、`LLMBranchOperator`…），业务用户无法理解
- **参数即元数据**：参数表单由 `IFlowNodeParameterUI.ui_type` 驱动（14 种 renderer），直接暴露 `type_cls` / `parent_cls` / `${key:name@scope}` 变量语法等引擎概念
- **连线即类型系统**：连线校验走 AWEL `type_cls`/`is_list`/`parent_cls` 匹配，报错信息是引擎层的
- **入口割裂**：流程列表藏在 `/construct/flow`，运行入口是「start chat」跳 `chat_flow` 场景，与首页数据分析体验（`pages/index.tsx`）完全脱节

### 1.2 改造目标

| 维度 | 现状 | 目标 |
|---|---|---|
| 节点粒度 | 技术算子（数百个） | **产品能力节点（P0 共 12 个）**，名字即业务语言：数据库查询、智能分析、可视化生成… |
| 模板 | 1 个数据分析模板（`chat-data-awel-flow-template.json`），不可发现 | **3 个内置模板**开箱即用，对话里直接选 |
| 入口 | `/construct/flow` 三级页面 | **首页 + 菜单一级入口**，选中即聊 |
| 运行体验 | 跳 `chat_flow` 场景，黑盒执行 | 对话内**步骤进度卡 + 每步可展开中间产物 + HITL 确认** |
| 自定义 | 只能拖拽 AWEL 算子 | 三级：改 prompt → 存「我的节点」→ 开发者模式写算子 |
| 引擎 | AWEL | **AWEL 不动**，新增产品层 TaskFlow DSL 编译到 AWEL FlowData |

---

## 2. 处置边界：废弃 / 保留 / 新增

### 2.1 废弃（产品层）

| 资产 | 处置 |
|---|---|
| `web/pages/construct/flow/`（list + canvas + libro） | 路由下线，菜单移除，旧链接 301 到新「任务流程」列表 |
| `web/components/flow/`（add-nodes-sider / canvas-node / node-param-handler / node-renderer×14 / node-handler…） | 随页面删除；`preview-flow.tsx`（只读 ReactFlow）保留供调试页复用 |
| 节点面板「高阶/全部」开关、AWEL 变量选择器、ui_type 表单引擎 | 概念废弃，不进新产品 |
| `locales/*/flow.ts` 旧 key | 清理，新建 `locales/*/taskflow.ts` |

### 2.2 保留（引擎层，全部不动）

- AWEL 内核：`DAG` / `BaseOperator` / `MapOperator` / `BranchOperator` / `JoinOperator` / runner / `JobManager`
- 触发器体系：`CommonLLMHttpTrigger`（对话触发）、`HttpTriggerManager`（`/api/v1/awel/trigger` 自动挂载）
- Flow 服务 API：`/api/v2/serve/awel/flows` CRUD、`/chat/flows`、`/flow/debug`（SSE）、`/flow/templates`、`/flow/export|import`（dbgpts）
- 对话执行通道：`POST /api/v1/chat/completions` + `chat_mode=chat_flow` + `select_param=<flow_uid>` → `flow_service.chat_stream_flow_str()` SSE 流
- 已有高阶算子：`HODatasourceExecutorOperator`（NL2SQL+执行+GPTVisMixin）、`HODatasourceDashboardOperator`、`CodeMapOperator`、`HOLLMOperator`/`HOStreamingLLMOperator`、`ReportAnalystOperator`、dbgpt-ext RAG 算子
- vis 协议：`vis-chart` / `vis-dashboard` / `vis_gpts_execution` / `vis_report_generation`，前端 gpt-vis 渲染链
- dbgpts 包管理（模板分发与导入导出）

### 2.3 新增

- **产品层 TaskFlow DSL**（JSON）+ **编译器**（DSL → AWEL FlowData）
- **12 个产品节点**（其中 8 个是对现有算子的产品化包装，4 个新写）
- 前端新页面：`/taskflow` 列表 + `/taskflow/editor` 编辑器
- 首页 `pages/index.tsx` + 菜单「任务流程」分组 + 对话内 `TaskFlowRunCard` 运行态组件
- 节点执行进度事件（新 vis tag `flow_step`，复用 SSE 通道）

---

## 3. 产品方案

### 3.1 概念模型

```
任务流程 TaskFlow        —— 一个有名字、有描述、可发布的分析流程（底层 = 一个 chat_flow 类 AWEL DAG）
├── 节点 Node            —— 产品能力单位（12 种），每个节点 = 1 个 AWEL 高阶算子的产品化包装
├── 模板 Template        —— 内置/社区分发的只读流程，用户「编辑副本」后变成我的流程
├── 运行 Run             —— 一次对话触发 = 一次 DAG 执行，节点状态实时回流对话
└── 我的节点 CustomNode   —— 用户把「配置好的节点」另存为私有节点（P1），或开发者注册 Python 算子
```

关键产品决策：

1. **流程默认线性**。P0 画布以「纵向步骤流」为主形态（连线上的 + 号插入节点），分支/并行作为节点属性（「与上一步并行」开关）而不是显式 DAG 编辑 —— 与参考稿一致，把 DAG 复杂度藏进引擎。
2. **一个流程 = 一个对话场景**。发布后的流程自动出现在首页 + 菜单与 `/chat/flows`，运行通道复用 `chat_flow`，不新造执行链路。
3. **节点配置只暴露业务字段**。例如「数据库查询」节点只有：数据源、查询方式（自然语言/SQL）、行数上限、只读保护；`type_cls`、stream 模式、cache 等引擎参数全部收敛进编译器默认值，高级用户走「开发者模式」。

### 3.2 节点体系（P0 共 12 个，4 组）

| 组 | 节点 | 一句话说明 | 底层实现（现有资产映射） | P0? |
|---|---|---|---|---|
| 边界 | **开始** | 读取分析目标与对话上下文（数据库/文件/知识库引用） | `CommonLLMHttpTrigger` + 上下文装配（复用 `ServePreChatHistoryLoadOperator`） | ✅ |
| 数据来源 | **数据库查询** | 选数据源，自然语言或 SQL，有界只读 | 包装 `HODatasourceExecutorOperator`（NL2SQL 走 chat_with_db_execute 同款 prompt） | ✅ |
| 数据来源 | **文件数据** | 上传 CSV/Excel 作为分析数据集 | 新算子 `HOFileDataOperator`（复用 chat_excel 的文件解析，落 DuckDB/pandas） | ✅ |
| 数据来源 | **知识库检索** | 检索知识库补充业务口径/术语 | 包装 dbgpt-ext `KnowledgeOperator` | P1 |
| 分析计算 | **数据清洗** | AI 生成 pandas 代码完成清洗转换 | 特化 `CodeMapOperator`（prompt 模板内置 + 沙箱执行） | P1 |
| 分析计算 | **智能分析** | 围绕分析目标执行计算，产出结论与中间表 | 新算子 `HODataAnalysisOperator`（LLM + `CodeAction` 循环，逻辑来自 `DataScientistAgent`/`data_analysis_planning_agent_example`） | ✅ |
| 分析计算 | **可视化生成** | 自动选图表类型，生成图表/仪表盘 | 包装 `HODatasourceDashboardOperator`（gpt-vis `vis-chart`） | ✅ |
| 流程控制 | **条件分支** | 按上一步结果路由（如「行数=0 → 走澄清分支」） | 包装 `LLMBranchOperator`/`BranchOperator` | P1 |
| 流程控制 | **人工确认** | 暂停等待人工检查后继续 | 新算子 `HOHumanConfirmOperator`（复用对话 HITL pending-question 机制，SSE 推确认卡） | ✅ |
| 流程控制 | **循环遍历** | 对列表数据逐条执行子流程 | `MapOperator` 展开 / `IteratorTrigger` | P2 |
| 结果输出 | **分析报告** | 汇总结论生成结构化报告 | 包装 `ReportAnalystOperator`（`vis_report_generation`） | ✅ |
| 结果输出 | **结果校验** | 口径核对与异常拦截，不通过则回退 | 特化 `LLMBranchOperator`（校验 prompt 内置） | P1 |
| 结果输出 | **消息推送** | 结果推 webhook/群机器人 | 新算子 `HOWebhookOperator` | P1 |
| 边界 | **输出** | 整理最终结果返回对话 | 终止算子（trigger response） | ✅ |

> P0 = 8 个执行节点 + 开始/输出；P1/P1 见第 7 章分期。节点面板按组着色：数据来源蓝 / 分析计算紫 / 可视化青 / 流程控制琥珀 / 输出绿（设计稿 SCREEN 01）。

### 3.3 内置模板（随包发布，`/flow/templates` 通道）

| 模板 | 节点链 | 场景 |
|---|---|---|
| **数据分析流** | 开始 → 数据库查询 → 智能分析 → 可视化生成 → 人工确认 → 分析报告 → 输出 | 常规经营分析，全流程样板 |
| **通用快速取数** | 开始 → 数据库查询 → 输出 | 有界只读查询，直接给答案和口径说明 |
| **Excel 透视分析** | 开始 → 文件数据 → 数据清洗 → 智能分析 → 可视化生成 → 输出 | 上传表格即分析 |

模板以新 TaskFlow DSL 重写（现有 `chat-data-awel-flow-template.json` 作为编译器正确性的对照样例），按 `templates/{en,zh}/` 双语落盘，由 `GET /flow/templates` 透出；首页 + 菜单与列表页直接消费。

### 3.4 首页对话集成（设计稿 SCREEN 02 / 04）

**选择**（改动点：`pages/index.tsx` 两处 `Dropdown menu.items`，约 3353 / 4076 行）：

- + 菜单新增「🧩 任务流程」分组 → 二级菜单 = `GET /api/v2/serve/awel/chat/flows` 返回的流程列表（内置模板在前，我的流程在后，底部「管理任务流程」跳 `/taskflow`）
- 选中后输入框上方挂 **流程 chip**（名称 + 节点数 + 移除 ✕），同时把流程默认数据源渲染为上下文 chip

**执行**：

- 发送时 `chat_mode=chat_flow`、`select_param=<flow_uid>`，走既有 `chat_stream_flow_str` SSE 通道，**不改后端执行链路**
- 对话内渲染 `TaskFlowRunCard`（新组件）：步骤时间线（进行中 spinner / 完成✓+耗时 / 待执行灰态 / HITL 琥珀态），每步可展开中间产物 —— SQL 块、数据表预览（vis-chart table）、结论摘要、图表（gpt-vis 直出）
- 人工确认节点触发时，卡片底部出 HITL 横幅（确认并继续 / 修改要求），复用 `ChatContentContext` 的 pending HITL question 机制
- 右侧 Artifact 面板（首页已有右栏预览能力）按 tab 聚合：图表 / 报告草稿 / 中间数据

### 3.5 编辑器交互（设计稿 SCREEN 01）

- **三栏**：左节点面板（搜索 + 4 组折叠 + 点击/拖拽加节点）｜中画布（reactflow 11 保留，纵向线性布局 + 连线 + 号插入 + 点选节点）｜右属性面板（业务字段表单，废弃 ui_type 引擎）
- **顶栏**：返回、流程名（点击改）、状态 tag（草稿/已发布）、试运行（复用 `/flow/debug` SSE）、导入导出（复用 dbgpts）、发布
- **自然语言改流程**（P1）：顶栏下常驻输入条，把「当前 DSL + 用户指令」发给 LLM 生成 DSL diff，用户确认后应用 —— 只操作产品层 DSL，不碰 AWEL
- **属性面板**：分组为 基本（名称/模型/业务 prompt）· 输入输出（只读展示契约）· 执行策略（并行开关/重试/超时 → 编译为 runner 参数）
- **校验产品化**：`checkFlowDataRequied` 那套引擎校验替换为业务校验（「数据库查询节点未选数据源」「可视化前没有数据节点」）

### 3.6 用户自定义节点（三级，粒度递进）

| 级别 | 形态 | 实现 |
|---|---|---|
| L1 改行为 | 节点业务 prompt 可编辑（分析要求/报告大纲/校验规则） | DSL `config.prompt_override`，P0 |
| L2 我的节点 | 把配置好的节点「另存为我的节点」，出现在节点面板「我的节点」组 | 新表 `taskflow_node_preset`（user + node_kind + config 快照），P1 |
| L3 开发者模式 | Python 写 AWEL 算子，`ViewMetadata.tags` 打 `taskflow` 标记即出现在节点面板「自定义」组；流程可切「开发者视图」查看编译后的 AWEL FlowData（只读） | 复用 `_OPERATOR_REGISTRY` + dbgpts 安装，P2 |

---

## 4. 技术方案

### 4.1 总体架构

```
┌─ 产品层（新）────────────────────────────────────────────┐
│  web/pages/taskflow/*   首页+菜单   TaskFlowRunCard        │
│         │ TaskFlow DSL (JSON, 产品节点+业务config)         │
├─ 适配层（新）────────────────────────────────────────────┤
│  TaskFlowCompiler: DSL ──► AWEL FlowData（节点展开/参数填充）│
│  TaskFlowNodeRegistry: 12个产品节点 ↔ AWEL算子映射/契约校验 │
│  flow_step vis 事件: 节点执行状态 ──► SSE                  │
├─ 引擎层（不动）──────────────────────────────────────────┤
│  AWEL DAG/runner/CommonLLMHttpTrigger/flow serve API      │
│  chat_stream_flow_str / dbgpts / vis 协议                  │
└──────────────────────────────────────────────────────────┘
```

### 4.2 TaskFlow DSL（产品层存储格式）

```jsonc
{
  "format": "taskflow/1",
  "nodes": [
    { "id": "n1", "kind": "start", "config": {} },
    { "id": "n2", "kind": "db_query", "config": {
        "datasource": "mysql_prod",      // 业务字段
        "query_mode": "nl",              // nl | sql
        "max_rows": 1000, "readonly": true
    } },
    { "id": "n3", "kind": "ai_analysis", "config": {
        "model": "deepseek-v3",
        "prompt_override": "关注趋势与同比环比…",
        "emit_dataset": true,            // 输出中间结果表
        "retry": 2, "timeout_s": 120, "parallel_with_prev": false
    } },
    { "id": "n4", "kind": "visualize", "config": { "max_charts": 4 } },
    { "id": "n5", "kind": "report", "config": { "format": "markdown" } },
    { "id": "n6", "kind": "output", "config": {} }
  ],
  "edges": [ ["n1","n2"], ["n2","n3"], ["n3","n4"], ["n4","n5"], ["n5","n6"] ],
  "viewport": {}
}
```

**编译器**（`dbgpt_serve/flow/taskflow/compiler.py`）把每个产品节点展开为 1..N 个 AWEL 算子并填充引擎参数：

- `db_query` → `HODatasourceRetrieverOperator`(schema 装配) + `HODatasourceExecutorOperator`（`max_rows→limit`、只读强制 `EXPLAIN`/SELECT 校验）
- `ai_analysis` → `HODataAnalysisOperator`（新，`LLMOperator`+`CodeMapOperator` 内循环封装）
- 开始/输出 → `CommonLLMHttpTrigger` + response 终止算子
- edges 按 DSL 顺序生成 `FlowEdgeData`（含 `source_order/target_order`）；`parallel_with_prev` 编译为分支 join 结构
- 编译结果走既有 `Service.create_and_save_dag` 建 DAG，**执行链路零新增**

### 4.3 存储与 API

- 复用 flow `ServeEntity` 表，新增两列（跟随 `define_type: json|python` 先例）：
  - `flow_format: "awel" | "taskflow"`（默认 awel，存量兼容）
  - `taskflow_source: TEXT`（产品层 DSL 原文；`flow_data` 列存编译后的 AWEL FlowData，双写）
- API 增量（挂在现有 flow router 下，不新开服务）：
  - `POST /flows` / `PUT /flows/{uid}`：请求带 `flow_format=taskflow` 时先编译再落库
  - `GET /flows/{uid}?format=taskflow`：返回 DSL 源（编辑器消费）
  - `GET /taskflow/node-kinds`：12 个产品节点的 manifest（名称/分组/图标/config schema/IO 契约），前端节点面板与属性表单由此驱动
  - `GET /chat/flows`：已有，前端 + 菜单直接用（响应里带上 `taskflow_source` 的模板标记即可）

### 4.4 运行进度事件

- 新 vis tag `flow_step`（`dbgpt/vis/tags/vis_flow_step.py`）：`{node_id, node_label, kind, status: running|success|failed|waiting_confirm, duration_ms, payload_ref}`；payload（SQL/表/结论）仍走既有 vis-chart/vis-code 消息
- 产品节点算子基类 `TaskFlowNodeMixin`：执行前后各 yield 一次 `flow_step`；HITL 节点 yield `waiting_confirm` 并挂起，确认后续跑（复用 conversation HITL 机制）
- 前端 `TaskFlowRunCard` 消费 SSE 中的 `flow_step` 序列渲染步骤卡；无 `flow_step` 的旧流程回退为现有 `vis_gpts_execution` 渲染（兼容）

### 4.5 前端改造清单

| 位置 | 动作 |
|---|---|
| `web/pages/construct/flow/` | 删除（先 301 到 `/taskflow`） |
| `web/components/flow/` | 删除，保留 `preview-flow.tsx` 移至 `components/taskflow/debug/` |
| `web/pages/taskflow/index.tsx` | 新增：列表页（模板/我的流程 tabs、卡片、运行统计） |
| `web/pages/taskflow/editor.tsx` + `components/taskflow/editor/*` | 新增：三栏编辑器（palette 静态 manifest 驱动 / canvas reactflow / 右栏属性表单） |
| `web/pages/index.tsx`（~3353、~4076 两处 menu.items） | + 菜单加「任务流程」级联（数据来自 `/chat/flows`），选中置 `flowChip` state，发送时带 `chat_mode=chat_flow&select_param` |
| `new-components/chat/content/` | 新增 `TaskFlowRunCard.tsx` + `flow_step` 消息解析（`utils/action-display.ts` 挂接） |
| `client/api/flow/index.ts` | 增补 `getNodeKinds`、`getFlow?format=taskflow` 类型 |
| `locales/{en,zh}/taskflow.ts` | 新增；清理 `flow.ts` 旧 key（en/zh 同步，遵循项目 i18n 约定） |

### 4.6 旧数据兼容

- 存量 `flow_format=awel` 的流程：**不迁移、可运行、不可在新编辑器打开**（列表默认隐藏，提供「旧版流程」筛选）；`chat_flow` 执行不受影响
- 内置模板一次性用 DSL 重写，旧 `chat-data-awel-flow-template.json` 留作编译器回归对照
- dbgpts 导入导出对两种格式都支持（导出时 taskflow 流程同时带 DSL 源与编译产物）

---

## 5. 分期计划

| 期 | 范围 | 验收 |
|---|---|---|
| **P0（3–4 周）** | 8+2 个节点（表 3.2 ✅ 列）；3 个内置模板；`/taskflow` 列表+编辑器（无 NL 改流程）；首页 + 菜单集成；`flow_step` 步骤卡 + HITL 横幅；旧 UI 下线 + 301；DSL 编译器 + 双写存储 | 首页选「数据分析流」连 mysql 提问，步骤卡逐步推进，SQL/表/图/报告可展开，人工确认可放行；旧链接跳转 |
| **P1（3 周）** | 知识库检索/数据清洗/条件分支/结果校验/消息推送 5 节点；NL 改流程；我的节点（L2）；定时触发（`IteratorTrigger` + cron 配置）+ 每日快报模板；运行统计落库（次数/成功率进列表卡片） | 可用 NL 在画布上插入节点；定时流程到点推送 webhook |
| **P2（2 周）** | 循环遍历节点；开发者模式（算子注册 + 编译产物只读视图）；模板中心接 dbgpts hub；流程版本管理 | 第三方 dbgpts 算子出现在节点面板并可运行 |

里程碑前置依赖：`HODataAnalysisOperator`（智能分析）与 `HOHumanConfirmOperator`（人工确认）是 P0 仅有的两个新算子，其余均为包装；这两个算子的验收标准 = 编译后的「数据分析流」模板端到端跑通。

## 6. 风险与开放问题

1. **DSL↔AWEL 双向漂移**：双写存储下若有人手改编译产物会失同步 → 产品层流程禁止直接 PUT `flow_data`（API 层拦截 `flow_format=taskflow` 的裸 flow_data 写入）。
2. **HITL 在 SSE 长连接上的挂起时长**：人工确认可能超过网关超时 → 确认等待不持有 SSE，走「断流 + 确认后续跑新流」（复用现有 HITL 恢复机制，P0 需联调验证）。
3. **智能分析节点的产出稳定性**：LLM+Code 循环的收敛性 → 限制最大迭代轮次与超时，`emit_dataset` 的中间表统一落会话临时存储（DuckDB），失败时步骤卡可重试单节点。
4. **旧 libro（notebook）流程**：`/construct/flow/libro` 一并下线，存量 python 流程仅保留 API 运行能力，不做新编辑器适配。
5. **开放**：定时触发是否要单独「任务实例」列表页（参考稿 DataWorks 有任务实例概念）——P1 设计时再定，P0 不做。

---

## 7. 产品展示

设计稿（HTML，直接浏览器打开）：`docs/design/taskflow-mockups/index.html`

| 屏 | 文件 | 内容 |
|---|---|---|
| SCREEN 01 | `01-flow-canvas.html` | 任务流程编辑器：12 节点四组面板 / 线性画布 + 号插入 / 业务属性面板 / NL 改流程入口 |
| SCREEN 02 | `02-chat-picker.html` | 首页 + 菜单「任务流程」级联 → 选中后流程 chip + 默认数据源上下文 |
| SCREEN 03 | `03-flow-list.html` | 流程管理：内置模板/我的流程分区卡片（节点链缩略图、运行统计、发布态） |
| SCREEN 04 | `04-flow-run.html` | 对话内运行态：步骤进度卡（SQL/表/结论可展开）+ HITL 横幅 + 右侧图表/报告 Artifact |

---

## 8. P0 实施注记（2026-10-04，已落地）

P0 已按本方案完成编码，以下为实施时确定的具体决策（与上文的差异点）：

1. **落地文件**
   - 后端：`dbgpt_app/operators/taskflow.py`（5 个新算子：`TFStepMarkerOperator` / `HOFileDataOperator` / `HODataAnalysisOperator` / `HOChartAdvisorOperator` / `HOHumanConfirmOperator`）；`dbgpt_serve/flow/taskflow/`（`dsl.py` + `nodes.py` 8 节点 manifest + `compiler.py` 编译器）；`FlowPanel` 新增 `flow_format` / `taskflow_source` 两字段（`ServeEntity` 加两列 + `migrate_flow_table_columns()` 自动 ALTER）；`Service.create_and_save_dag` / `update_flow` / `debug_flow` 三处挂编译钩子；`GET /api/v2/serve/awel/taskflow/node-kinds` manifest 端点；模板 zh/en × 3（taskflow-*-template.json）。
   - 前端：`pages/construct/taskflow/`（列表，ConstructLayout 新 tab，替换原 `awel_flow` tab）；`pages/taskflow/editor.tsx` + `components/taskflow/editor/*`（三栏编辑器，reactflow 只读画布 + 连线 + 号插入 + manifest 驱动属性面板 + 试运行抽屉）；`pages/index.tsx`（两处 + 菜单级联、flow chip、`performFlowStart` 走 `/api/v1/chat/completions` `chat_flow` 通道）；`pages/construct/flow/*` 三个旧页面替换为重定向到 `/construct/taskflow`；`locales/{en,zh}/taskflow.ts`。
2. **步骤进度协议**：未新增 `flow_step` vis 类。每个产品节点的 view 输出经 `TFStepMarkerOperator` 在文本前插入 ` ```vis-flow-step ``` ` 标记块（含 step_id/label/kind/duration），最终 join 文本携带全部标记；前端 `parseTaskflowStream` 解析为步骤序列并**复用首页既有 Manus 步骤 UI**（`ExecutionStep.status` 扩展 `pending`），数据通道（markdown/结论）不带标记，不污染下游 LLM 输入。
3. **P0 范围收敛**：
   - 人工确认节点为**软确认**（保序 + 步骤标记，不中断 DAG）；真正暂停/恢复依赖对话 HITL 通道，P1 实现。
   - `chat_flow` 通道为非增量单次返回，步骤卡进度在收到完整响应后按标记一次性呈现（流式过程中的"运行中"态由 DSL 预置步骤列表驱动）；节点级实时流式进度 P1 再议。
   - 执行策略字段（并行/重试/超时）在 DSL 中保留但未接线（`RESERVED_CONFIG_KEYS`）。
   - 编辑器画布为线性只读视图（节点锁定、自动纵向布局），插入/删除/配置即完成编辑，不提供自由拖拽连线。
4. **验证**：后端 46 个 flow 测试全绿（新增 16 个：DSL 校验 ×6、manifest ×2、编译 ×4、marker ×3、三模板 DAG 构建 ×3，用 stub 的 `local_db_manager` 跑通 `FlowFactory.build`）；前端 `tsc --noEmit` 对新增文件零错误（`pages/index.tsx` 维持基线 13 个存量错误），ESLint/prettier 通过。
5. **运行态二次迭代（对齐设计稿 04，2026-10-05）**：
   - **每节点真实耗时**：编译器在 trigger 后插入零开销 `TFStepClockOperator`（写 DAG 启动时间戳到 share data，所有 question 输入经它透传）；`TFStepMarkerOperator` 用时间戳链计算每个产品节点的执行耗时写入标记（`duration_ms`），db_query 步骤附带结果行数摘要（读 executor 共享 df）。
   - **步骤可展开看输入输出**：`parseTaskflowStream` 扩展出按节点分段的 `sections`（标记 + 段内容 + 段外 residual）；消息保留原始文本（标记不剥离），`ManusLeftPanel` 新增 `flow_node` 步骤类型与 `FlowStepRow` 渲染——流程卡片整体包裹（流程名 + 进度条 + x/y），每步显示耗时/行数徽标，点击展开内联渲染 SQL/结果表/结论（走既有 gpt-vis markdown 管线）；卡片下方只显示 residual 叙述文本。
   - 修复：SSE 通道 `\\n` 转义未还原导致标记泄漏正文；i18next 插值需 `{{count}}`；`getTypeLabel` 空串 falsy 回退 "Action"。

