# 🛠️ db-ops · 智能运维（官方场景套件）

> 原生 plugin ｜ `name: db-ops` ｜ `version: 1.1.0` ｜ `dbgpt.scenario_id: ops` ｜ `dbgpt.execution: react`
> DB-GPT 数据 Agent 三个官方场景套件之一（另两个：`db-query` 智能取数、`db-analysis` 智能分析）。
> 一句话：**一个 ReAct agent + 三个套件** —— 套件是"会话级声明式配置束"，agent 是执行器；**套件只声明，核心来执行**。

---

## 1. 定位

`db-ops` 面向**企业业务库（OLTP，非数仓）**的智能运维工作台，把 DBA 的日常作业收敛成一条可复核的链路：

```
采集慢日志/EXPLAIN → 聚合多维信息 → 根因定位 → 诊断报告 → 修复提案（不执行）
```

它解决的典型问题：
- 「订单库昨晚 22:00-02:00 为什么慢？」—— 慢查询根因定位，带证据链；
- 「这个生产库健康吗？多久会出事？」—— 多维巡检 + 容量触顶天数外推；
- 「orders 表该加什么索引？加了有什么风险？」—— 索引候选 + 收益/代价量化 + 变更评审；
- 「库越来越大，怎么系统性瘦身？」—— 数据库画像与治理路线图；
- 「这条 DDL 生产能改吗？」—— 破坏性分级、锁影响预估、在线方案、回滚预案、审批判定。

**与其它两个套件的分工**：取业务数据 → `db-query`；做多步分析与图表报告 → `db-analysis`；**保障库的健康与安全变更** → `db-ops`。跨场景连环任务（问数发现慢 → 转运维诊断）由核心的场景切换机制处理：切换是一次 timeline 事件，历史不丢，工具白名单与审批策略随之更换。

### 这个套件的特殊性（务必先读）
`db-ops` 是三个官方套件中**唯一包含破坏性操作**（DDL / ANALYZE）的套件，因此**审批最严**：
- 破坏性工具每次调用都触发审批 dock，**不适用**记忆白名单；
- **生产环境 DDL 默认 `deny`**，只出提案，需走线下变更流程；
- **修复动作永远是"提案 + 人确认"**，套件不自动执行任何变更。

---

## 2. 能力清单

| 能力 | 说明 | 主要工具 | 产物 |
|---|---|---|---|
| 慢查询诊断 | 建负载基线 → 慢日志指纹聚合 → EXPLAIN 判读 → 根因归类（缺索引/坏计划/锁等待/大扫描/写法/资源/膨胀） | `db_metrics`、`slow_log`、`explain`、`index_info` | `diag_report`、`fix_plan` |
| 健康巡检 | 六大类多维基线（连接/QPS、慢查询率、缓冲池、磁盘、复制、锁事务）+ 三级判据 + 容量触顶外推 | `db_metrics` | `diag_report`、`citation` |
| 索引优化 | 从真实查询模式生成组合索引/覆盖索引候选，识别重复与未使用索引，量化写入放大与空间代价 | `index_info`、`slow_log`、`explain` | `fix_plan`、`execution_plan` |
| 画像与治理 | 表膨胀/碎片/无主键/大字段/冷热混存识别，A/B/C 三层治理路线图 | `db_metrics`、`index_info`、`schema_link` | `diag_report`、`fix_plan` |
| 受控 DDL 评审 | 破坏性分级 L0-L3、锁与耗时预估、在线 DDL 选型（INPLACE/gh-ost/pt-osc）、回滚预案、审批判定 | `index_info`、`db_metrics`、`explain`、`schema_link` | `fix_plan`、`execution_plan` |
| 影响面评估 | 表的业务归属、owner、下游数据集与同步链路（语义层可选，缺失时降级） | `semantic_search`、`schema_link` | `citation` |

**只读优先**：上表中除 `ddl` / `analyze` 外全部为只读工具，无需审批；采集阶段绝不触碰变更。

---

## 3. 内含技能（`skills/`，走现有 skill registry，SKILL.md 格式不变）

| 技能 | 路径 | 一句话 |
|---|---|---|
| `slow-query-diagnosis` | `skills/slow-query-diagnosis/SKILL.md` | 慢查询采集、EXPLAIN 判读表、根因归类与诊断报告 |
| `health-inspection` | `skills/health-inspection/SKILL.md` | 多维基线巡检、阈值判据、健康分与容量外推 |
| `index-advisor` | `skills/index-advisor/SKILL.md` | 索引候选生成（列序规则）、冗余识别、代价量化 |
| `profile-governance` | `skills/profile-governance/SKILL.md` | 数据库画像、五类治理问题、分层治理路线图 |
| `safe-ddl-review` | `skills/safe-ddl-review/SKILL.md` | 破坏性分级、锁影响预估、在线 DDL 选型、审批判定（**安全闸门**） |

配套运维手册（`runbooks/`，供人和 Agent 共同参考）：

| 手册 | 路径 | 内容 |
|---|---|---|
| 慢查询根因定位手册 | `runbooks/slow-query-rootcause.md` | 症状分诊 → 采集动作清单 → EXPLAIN 判读表 → 根因分类与修复动作/风险等级 → 定位决策树 → 报告模板 → 失败降级 |
| 生产安全变更清单 | `runbooks/production-safety-checklist.md` | 三条底线 → 破坏性分级 L0-L3 → 审批矩阵 → 禁止项红线 → 变更前/中/后清单 → 回滚预案模板 → 责任边界 |

SOP（注入 system prompt）：`prompts/ops-playbook.md` —— DBA 角色定位、诊断五步链、完整 worked example（订单库昨晚慢查询逐步 trace）、破坏性操作铁律、只读优先、失败与降级、终止条件。

---

## 4. 快捷命令（`/command`，会话内显式调用；与自动路由形成双轨）

| 命令 | 作用 | 绑定技能 |
|---|---|---|
| `/slowlog` | 按时间窗采集并聚合慢查询（Top N 指纹） | `slow-query-diagnosis` |
| `/explain` | 解读一条 SQL 的执行计划并指出坏计划原因 | `slow-query-diagnosis` |
| `/inspect` | 目标库健康巡检并出报告（六大类指标 + 健康分） | `health-inspection` |
| `/index` | 基于真实查询模式输出索引优化建议（仅提案） | `index-advisor` |
| `/profile` | 生成数据库画像与治理建议（膨胀/碎片/无主键/大字段/冷热） | `profile-governance` |
| `/fix` | 把本次诊断的修复动作整理为 `fix_plan`（分级/锁影响/在线方案/回滚/审批） | `safe-ddl-review` |

命令中的 `{target_db}` / `{time_window}` 由会话绑定上下文自动填充；未绑定时先澄清，不默认全库。

---

## 5. manifest 关键值（评审重点）

### 5.1 工具白名单
```yaml
tools:
  allow: [slow_log, explain, db_metrics, index_info, semantic_search, schema_link, analyze, ddl]
  deny:  [shell, drop_database, truncate]
  gated: [analyze, ddl]        # 破坏性：每次调用必过审批 dock，不得进入 auto/always 白名单
  read_only: [slow_log, explain, db_metrics, index_info, semantic_search, schema_link]
```
- **无 `shell`、无 `sql_execute`**：不能绕过工具执行任意 SQL，也不能在运维会话里跑业务取数。
- `allow` 与核心工具注册表**求交**后交核心 gate 执行；`gated` 是声明性标注，实际拦截由核心决定。

### 5.2 审批加严（`approval_overrides`）——**只能加严，不能放宽**
```yaml
approval_overrides:
  - match: {tool: ddl}                                  # → confirm：DDL 破坏性，生产强制确认
  - match: {tool: analyze}                              # → confirm：锁表/资源影响
  - match: {tool: ddl, env: production}                 # → deny：生产库 DDL 默认拒绝，需走变更流程
  - match: {tool: ddl, sql_pattern: "^(DROP|TRUNCATE|RENAME)"}   # → deny（永久）：不可逆
  - match: {tool: analyze, env: production, est_table_rows: ">10000000"}  # → confirm（加严）：大表避峰
  - match: {tool: ddl, phase: plan}                     # → confirm：先出执行计划卡（计划确认）
  - match: {tool: slow_log, env: production, est_scan_gb: ">50"}  # → confirm：大窗口日志采集也是高代价读取
```
**合并顺序恒为：`core deny > suite > core default`。**
- 套件可以把 `auto` 加严成 `confirm`、把 `confirm` 加严成 `deny`；
- 套件**不能**把核心 `deny` 放宽为 `confirm`/`auto` —— 试图放宽会被核心在 policy 构建期拒绝（有单测覆盖）；
- 合并发生在**策略构建期**，gate 执行期不感知套件 ⇒ 安全边界不插件化。

### 5.3 默认绑定：目标库 + 时间窗（运维场景的强约束）
```yaml
context_defaults:
  target_db: required        # 头部常驻 chip：一切动作的作用域
  time_window: required      # 头部常驻 chip：慢日志/指标采集区间
  datasource: session
  semantic_layer: optional   # 仅用于影响面/血缘与口径解释
  env: session               # dev/test/staging/production，由数据源元信息带入，套件不可覆盖
  time_window_defaults: {preset: last_4h, granularity: 5m, max_span: 7d}
```
- **两者缺一不进入采集阶段**（`bind_hint` 会提示用户先选目标库与时间窗）；
- 时间窗必须落成**绝对区间**（"昨晚" → `2026-10-21T22:00/2026-10-22T02:00`）并回述确认，避免跨轮漂移；
- `env` **读不到时按 `production` 处理**（就高不就低），并在报告水位线标注；
- 单次窗口 ≤7 天，超限分段采集，避免诊断本身压垮生产库。

### 5.4 产物与输出契约
```yaml
artifacts: [diag_report, fix_plan, execution_plan, citation]   # 全部引用核心渲染器注册表
output_contract: diag_report+fix_plan
```
完成标准：**未产出 `diag_report` 不得 `terminate`**；修复动作未标注"待审批/需人工确认"不得 `terminate`；任何 DDL/ANALYZE 在获批前不得出现在已执行轨迹中。

### 5.5 语义层消费策略
```yaml
semantic:
  layer: mysql_prod
  require: optional          # 运维以物理层为主，语义层可选（影响面/血缘）
  consumption: rule_first    # 护栏/规则优先，指标次要
  pin: {policy: latest_published}
  fallback: db_summary       # 语义层未就绪时由 binder 降级为 DBSummary，并在水位线标注
```

### 5.6 路由与推荐问题
```yaml
routing:
  keywords: [慢查询, 巡检, 根因, 诊断, 索引, 优化, 健康, profile, 治理, 执行计划, 锁]
  specificity: 0.9           # 与 db-query/db-analysis 关键词重叠时的优先级因子
  tie_break: llm_intent      # 平局交 LLM 意图判定
  negative_keywords: [导出, GMV, 环比, 报告分享]   # 降低误路由（取数/分析场景词）
```
首页推荐问题（Tab 数据源，同时是套件 eval set 的种子）：`订单库昨晚慢查询根因`、`生产库健康巡检出报告`、`生成数据库 profile 与治理建议`、`orders 表该加什么索引`、`这条 SQL 为什么走了全表扫`、`给 payment 表加索引的变更风险有多大`。路由准确率自测目标 ≥90%。

---

## 6. 安全边界（什么留在核心，什么在套件）

### 6.1 留在核心，**不可插件化**
| 核心能力 | 为什么不能进套件 |
|---|---|
| ReAct 循环与 planner | 引擎只有一个；为三场景各建一个 agent 会把记忆/评测/护栏/溯源各 fork 一份 |
| **审批 gate 的执行** | 套件只**声明**策略规则，拦截与放行由核心统一执行；执行期不感知套件 |
| 沙箱 | 工具隔离与资源限制的 enforcement 点 |
| 渲染器注册表 | 套件声明产物卡类型 + 参数，**不带任何前端代码** |
| 语义层与 SemanticRetriever | 权威定义存储与检索属核心地基 |
| 会话/记忆、引用溯源、点赞自进化闭环 | 跨场景共用的平台能力 |

### 6.2 进套件的（声明式载荷）
SOP/playbook、工具白名单、默认绑定、产物声明、审批 overrides（**仅加严**）、推荐问题与路由词、内含 skills、编排策略（`execution: react|flow`）。

### 6.3 三条铁律
1. **策略只能加严**：`core deny > suite > core default`。套件试图放宽核心 deny 会被拒绝（P0 单测覆盖）。
2. **生产破坏性操作默认 deny**：`env=production` 时 DDL 不发起调用、不"先试试看"，直接输出提案 + 线下变更流程指引（变更单 + 备份验证 + 双人复核 + 低峰窗口 + 变更后验证）。`env` 未识别按 production 处理。
3. **修复永远是提案**：`fix_plan` 每条动作必须含分级（L0-L3）、预估收益、锁与资源影响、在线方案、**回滚预案**、审批要求，并统一标注"**未执行 · 待人工确认**"。无回滚预案的提案评审不通过。

### 6.4 破坏性分级速览
| 级别 | 定义 | 例 | 非生产 | 生产 |
|---|---|---|---|---|
| L0 | 只读 | `EXPLAIN`、查指标/索引 | auto | 允许 |
| L1 | 低风险、不重建 | 小表 `ADD INDEX`、`ANALYZE`（中小表） | confirm | deny → 变更流程 |
| L2 | 重建/长 IO/短暂锁/数据搬迁 | 大表 `ADD INDEX`、`OPTIMIZE`、分区改造、分批归档 | confirm + 在线方案 + 回滚 | **deny** → 变更流程 |
| L3 | 高风险/不可逆 | 改主键、改列类型、大表数据清理、`RENAME`、`DROP`/`TRUNCATE` | confirm + 双人复核 + 演练 | **deny（永久）** |

### 6.5 其它红线（详见 `runbooks/production-safety-checklist.md`）
- `ddl` / `analyze` **不适用** once/session/always 记忆白名单，每次都问；
- **被拒绝后不绕行**：不改参数重试、不换等价工具、不拆批规避阈值、不伪装成只读查询；
- `EXPLAIN ANALYZE` **视同执行**（会真实运行语句），写语句一律禁用；
- **一次窗口只推一条破坏性动作**，禁止打包；
- MDL 前置检查：存在长事务时不得执行 `ALTER`；重建类操作需约等量空闲磁盘；
- 归档清理必须"先归档 → 校验 → 保留可恢复期（≥30 天）→ 再分批清理"，并核对合规留存期；
- 全程留痕（`tool_call`、`approval_decision`、`suite_version`、`target_db`、`time_window`、`env`），审计可回答"这份诊断是哪个套件版本、哪个库、哪个窗口跑出来的"。

---

## 7. 对话流与工作台表现（§7.4）

```
用户提问（自动路由命中运维关键词 / 点击推荐问题 / 显式 /命令）
  → 头部 chip：🛠️ db-ops@1.0.0 ｜ 目标库 orders_prod ｜ 时间窗 22:00-02:00 ｜ 环境 production（红标）
  → 意图识别
  → 采集执行计划/慢日志（只读工具，左栏 timeline 分组工具行）
  → 聚合多维信息
  → 根因定位
  → 诊断报告卡（慢查询表 + 修复建议）  ← 右栏查看器：根因详情 / 执行计划 / 血缘影响
  → 修复类操作（DDL/ANALYZE）弹审批 dock：破坏性标识 + 生产标识 + 影响面 + 预估耗时/锁范围 + 回滚 + 批准/拒绝/替代方案
  → 生产 deny 时：不发起调用，输出提案 + 变更流程指引
  → terminate（1-2 句摘要：根因 + 首要提案 + 审批状态）
```

产物卡类型（`diag_report` / `fix_plan` / `execution_plan` / `citation`）由**核心渲染器注册表**提供，套件不带 UI 代码。

---

## 8. 安装与启用

### 8.1 官方内置（随仓库出货，dogfood 运行时）
本套件位于 `assets/suites/db-ops/`，与 `db-query`、`db-analysis` 同为官方内置套件，loader 启动时扫描入库。目录结构：
```
assets/suites/db-ops/
├── .qwenwork-plugin/plugin.json            # 唯一 manifest：原生元数据 + dbgpt 扩展
├── README.md                               # 本文件
├── prompts/ops-playbook.md                 # SOP，注入 system prompt
├── skills/
│   ├── slow-query-diagnosis/SKILL.md
│   ├── health-inspection/SKILL.md
│   ├── index-advisor/SKILL.md
│   ├── profile-governance/SKILL.md
│   └── safe-ddl-review/SKILL.md
└── runbooks/
    ├── slow-query-rootcause.md
    └── production-safety-checklist.md
```

### 8.2 通过 API 管理（P0）
| 操作 | 端点 |
|---|---|
| 列出套件（含版本/状态/推荐问题） | `GET /api/v1/suites` |
| 启用 | `POST /api/v1/suites/db-ops/enable` |
| 停用 | `POST /api/v1/suites/db-ops/disable` |

启用后：首页出现「🛠️ 智能运维」场景 Tab 与推荐问题，`routing.keywords` 参与自动路由评分；停用后从首页移除（**进行中对话保留 pin 版本直至结束**）。启用/停用按**工作空间（实例）级**生效。

> ⚠️ 启用前置：`requires.approval_gate = required`、`requires.sandbox = required`。**审批 gate 不可用时本套件不得启用**（破坏性工具无法拦截）。`semantic_layer` 为 optional，缺失时降级 DBSummary 不报错。

### 8.3 zip 上传（企业专属，P1）
把 `db-ops/` 目录打包为 ZIP（包内含 `.qwenwork-plugin/plugin.json`）经套件管理页上传。DB-GPT 特有配置位于 `dbgpt` 扩展，原有审批声明和工具边界保留；企业可定制阈值、runbook 与审批要求，核心权限和审批仍控制执行。

### 8.4 校验
manifest 必须能被 `yaml.safe_load` 解析；校验策略为 **fail-soft**（必填字段存在 + 类型粗检 + 缺省补全，坏字段跳过并告警，不引入 jsonschema 依赖）：
```bash
cd <repo> && python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('assets/suites/db-ops/**/*.yaml',recursive=True)]; print('YAML OK')"
```

---

## 9. 版本 pin 与升级

| 机制 | 行为 |
|---|---|
| 对话创建 | 写入 `ext_info.suite = db-ops@1.0.0`（`pin.policy: exact`），timeline 记录套件版本 |
| 套件升级 | **只影响新对话**（`upgrade_scope: new_conversation_only`）；历史对话不随升级漂移 |
| 会话内升级 | 需**显式动作**（`in_session_upgrade: explicit`，P1）：写新轮 `ext_info` + 一条 timeline 事件，历史不丢 |
| 场景切换 | 一次 timeline 事件（如"问数 → 运维"）：重绑上下文、换工具白名单与审批策略，历史不丢 |
| 审计 | 可回答"这次诊断结论是哪个套件版本、基于哪个库/时间窗/环境跑出来的"，`replayable: true` |

变更日志：`1.0.0`（2026-10-22）—— 首个官方版本：5 技能 + 2 runbook + ops-playbook SOP；DDL/ANALYZE 全量加严，生产 DDL 默认 deny。

---

## 10. 与核心的边界（速查）

| 事项 | 套件（db-ops） | 核心 |
|---|---|---|
| 角色与 SOP | ✅ 声明 `sop: prompts/ops-playbook.md` | 注入 system prompt |
| 工具能力 | ✅ 声明 `allow` / `deny` / `gated` | 提供工具实现，与 allowlist **求交**后交 gate |
| 审批策略 | ✅ 声明 `approval_overrides`（**仅加严**） | **执行**拦截/放行；policy 构建期合并（`core deny > suite > core default`） |
| 默认绑定 | ✅ 声明 `context_defaults` | 会话创建/每轮开始时 binder 绑定并渲染头部 chip |
| 产物 | ✅ 声明 `artifacts` 类型 | 渲染器注册表提供实现（套件**不带前端代码**） |
| 路由与推荐问题 | ✅ 声明 `routing` / `recommended_questions` | 首页 Tab、composer 路由评分与渲染 |
| 技能 | ✅ 内含 5 个 SKILL.md | 复用现有 skill registry 与 `_skill_tools` 加载通道 |
| 编排 | ✅ 声明 `execution: react`（`flow` 为 P1 保留） | ReAct 循环与 planner 执行；`flow` 时引用 AWEL flow |
| 语义层 | ⚪ 声明消费策略（`rule_first`、`optional`） | SemanticRetriever、权威定义存储、发布管道 |
| 沙箱 / 记忆 / 溯源 / 点赞闭环 | ❌ 不涉及 | 全部在核心 |

**反向提醒**：不要为运维场景单独建一个 agent —— 那会把记忆、评测、护栏、溯源各 fork 一份，套件化就白做了。差异落在套件，引擎始终是一个。

---

## 11. 已知边界与后续（P1/P2）

- **P0 不含 `execution: flow`**：字段保留，值仅 `react`。若巡检需固定管线（如报告生成走确定性后处理），P1 再接 AWEL flow。
- **配置类变更不在能力范围**：无 `shell`、无配置写入工具，参数调整（`innodb_buffer_pool_size`、隔离级别、超时等）只出建议 + 影响评估，执行走变更流程。
- **事故响应不在范围**：实例不可连通、主库宕机、数据损坏属应急流程，巡检会立即上报并提示人工介入，不在套件内处置。
- **P1**：套件管理页（安装/启用/升级/卸载、zip 上传、企业专属、推荐问题可编辑）、`/commands` 详情页、会话内显式升级。
- **P2**：市场发布、策略合并 UI 与按套件版本审计、"一句话生成场景套件"（meta-agent）。
- **阈值本地化**：巡检阈值与破坏性分级为套件默认值，企业可 fork 覆盖，冲突时**取更严的一侧**。

---

## 12. 许可

MIT · Author: DB-GPT Official ｜ Maintainers: data-agent-core
