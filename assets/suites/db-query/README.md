# 🔍 db-query · 智能取数（官方场景套件）

> `db-query@1.0.0` · 作者 `@DB-GPT 官方` · 分类 `official`
> 三个官方场景套件之一（`db-query` 取数 / `db-analysis` 分析 / `db-ops` 运维）。
> 设计依据：`docs/design/data-agent-product-design.md`（§4.1 六维配置束、§5.2 manifest、§7.2 智能取数工作台）、`docs/design/scenario-suite-impl-plan.md`（manifest P0 字段约定）。
> 双重规范：本套件同时符合 **DB-GPT scenario-suite 规范**（`suite.yaml` loader 契约）与 **AntWork 专家套件规范**（`.qoder-plugin/plugin.json` + `SKILL.md` 双语 frontmatter + `CONNECTORS.md`），可被两侧运行时直接加载。

---

## 一、定位

**自然语言 → SQL 精准取数能力包。**

面向企业业务库（非数仓）的取数场景：强制绑定语义层（表白名单 + 指标口径 + 默认过滤 + 行级权限规则），SQL 经 NL2SQL 生成并通过 `sql.validate` 自纠后在**只读从库**执行；高代价扫描按预估成本触发审批 `confirm`；答案下附**引用溯源 chips**（指标版本 / 表 / 样例 / 规则），👍 沉淀样例库、✏️ 纠错进语义标注待审队列。

角色定位是**精准取数员**，流程四拍：**schema-link → SQL → 执行 → 预览**。

它**不是**：数据分析报告工具（那是 `db-analysis`）、数据库运维诊断工具（那是 `db-ops`）、SQL 教学助手。

> **套件 vs 核心**：套件 = 会话级声明式配置束；agent = 执行器。一个 ReAct 运行时 + 三个套件，每个对话 = 被某个套件配置出来的一个 agent 实例。

---

## 二、能力清单

| 能力 | 说明 | 落点 |
|---|---|---|
| 语义双路召回 | 向量 top-k（按 `type` 过滤）+ 结构化精确匹配（同义词/指标名） | `semantic_search` / `semantic-linking` |
| 权威口径回源 | 按 `metadata.id` 回结构化库加载公式/默认过滤/join 路径/规则（向量只是索引不是真相） | `semantic.get_metric` / `metadata.get_table` |
| 精准 NL2SQL | 四要素齐备（指标表达式 + 默认过滤 + join 路径 + 表白名单）才生成；`sql.validate` 自纠最多 2 轮 | `nl2sql` / `nl2sql-precision` |
| 只读安全执行 | SELECT-only、超时 30s、预览 1000 行、只读从库路由、行级权限注入 | `sql_execute` / `readonly-guardrails` |
| 成本闸门 | `est_scan_gb > 100` / `est_scan_rows > 5000 万` / 缺时间过滤 → 审批 `confirm` | `approval_overrides` |
| 结果导出 | CSV/Excel，列类型保真（金额精度、长数字防科学计数法）、PII 强制脱敏、> 10 万行走审批 | `export_csv` / `result-export` |
| 引用溯源 | 每次回答挂 chips：指标（含版本）/ 表（含标注状态）/ 样例（命中编号）/ 规则（注入的过滤） | 核心渲染器 `citation` |
| 自进化闭环 | 👍 → 沉淀 Verified 样例（`use_count + 1`）；✏️ → 语义提案进待审队列，**不直接改权威源** | `few_shots` + `semantic.proposals` |
| 语义层降级 | 语义层未就绪时 fail-soft 降级 `DBSummary` 表摘要，并**显式标注水位线**，不报错不中断 | binder（核心） |

---

## 三、目录结构

```
assets/suites/db-query/
├── suite.yaml                        # manifest：套件入口文件（loader 解析契约）
├── README.md                         # 本文件
├── prompts/
│   └── query-playbook.md             # SOP 行事规程，注入 system prompt
├── skills/
│   ├── semantic-linking/SKILL.md     # 语义召回与权威口径加载
│   ├── nl2sql-precision/SKILL.md     # 精准 NL2SQL 与校验自纠
│   ├── readonly-guardrails/SKILL.md  # 只读安全执行与成本护栏
│   └── result-export/SKILL.md        # 结果集导出 CSV/Excel
└── few_shots/
    └── verified-queries.yaml         # Verified Q→SQL 样例库（few-shot + eval set，8 条）
```

---

## 四、内含 skills（4 个）

| 技能 | 职责 | 主用工具 |
|---|---|---|
| `semantic-linking` | 双路召回 → 按 id 回源加载权威定义 → 取枚举 → 取 few-shot → 取规则护栏 | `semantic_search`、`schema_link`、`semantic.get_metric`、`metadata.get_table`、`semantic.get_examples`、`guardrails.get_rules` |
| `nl2sql-precision` | 组装口径 prompt（指标/默认过滤/join/白名单/枚举/few-shot）→ 生成 → `sql.validate` 自纠 → 产出带来源注释的 SQL 卡 | `nl2sql`、`sql.validate` |
| `readonly-guardrails` | 执行前门禁复查 → 成本预估与审批判定 → 只读从库执行（超时/行数/行级权限）→ 异常处理与审批决议回灌 | `sql_execute` |
| `result-export` | 确认导出对象（口径不漂移）→ PII 脱敏 → 行数上限审批 → 落盘 → 列类型保真校验 → 交付与溯源 | `export_csv`、`guardrails.get_rules` |

技能格式遵循现有内置 SKILL.md 规范：frontmatter 仅 `name` + `description`，正文含技能目标 / 核心工作流程 / 完整流程示例 / 注意事项。

---

## 五、快捷命令（/command）

会话内可显式调用，详情页展示；显式命令优先于自动意图路由，但与护栏冲突时**护栏优先**。

| 命令 | 作用 | 主用技能 |
|---|---|---|
| `/nl2sql` | 自然语言→SQL 并在只读从库执行（引用指标口径与默认过滤） | `nl2sql-precision` |
| `/schema` | 查看目标表结构、语义标注与白名单状态 | `semantic-linking` |
| `/metric` | 查询指标定义、版本与默认过滤（权威口径回源） | `semantic-linking` |
| `/export` | 导出当前结果集为 CSV/Excel（列类型保真 + 脱敏） | `result-export` |

---

## 六、manifest 关键值

| 字段 | 值 | 说明 |
|---|---|---|
| `kind` | `scenario-suite` | 套件包类型标识 |
| `name` / `display` | `db-query` / 智能取数 | slug 全局唯一 |
| `version` | `1.0.0` | 对话创建时 pin，见第八节 |
| `scenario_id` | `query` | 对应首页场景 Tab |
| **`execution`** | **`react`** | P0 仅 `react`（自由 ReAct）；`flow` 为 P1 预留 |
| `sop` | `prompts/query-playbook.md` | 包内相对路径，注入 system prompt |
| **`tools.allow`** | **`[semantic_search, schema_link, nl2sql, sql_execute, export_csv]`** | binder 与核心 gate 求交后生效 |
| `tools.deny` | `[ddl, shell]` | 问数场景**无 ddl**，破坏性能力显式排除 |
| `tools.provide_mcp` | `[]` | 不自带 MCP server，全部复用核心内置工具 |
| **`context_defaults`** | **`semantic_model: required`、`datasource: session`、`time_window: session`** | 语义模型为**必需**绑定 |
| `artifacts` | `[sql_card, result_table, citation]` | 引用核心渲染器注册表，**不自带前端代码** |
| `output_contract` | `result_set+sql` | 完成标准：结果集 + 可复跑 SQL，二者缺一不可 `terminate` |
| `semantic` | `layer: mysql_prod`、`require: required`、`consumption: metric_first`、`pin.policy: latest_published` | 见第七节 |
| `routing.keywords` | `[查, 统计, 导出, GMV, 客单价, top, 环比, 明细]` | 首页自动路由评分依据 |
| `few_shots` | `few_shots/verified-queries.yaml`、`writeback: on_thumbs_up` | 样例库兼 eval set |

### `approval_overrides`（**仅可加严**）

合并顺序：**`core deny` > `suite` > `core default`**。套件只能加 `confirm`/`deny`，**不能**把核心 `deny` 放宽成 `auto`——试图放宽的规则会在 `merge_suite_overrides` 阶段被拒绝（有单测覆盖）。

| match | action | reason |
|---|---|---|
| `{tool: sql_execute, est_scan_gb: ">100"}` | `confirm` | 高代价扫描 |
| `{tool: sql_execute, est_scan_rows: ">50000000"}` | `confirm` | 超大行数扫描（预估 > 5000 万行） |
| `{tool: sql_execute, without_time_filter: true}` | `confirm` | 缺少时间范围过滤的全表聚合 |
| `{tool: export_csv, row_count: ">100000"}` | `confirm` | 大批量导出（> 10 万行）需确认脱敏与落盘范围 |

核心默认：只读 `SELECT` = `auto`（不打扰用户）。上表是在此基础上的**加严**。

> enforcement 发生在核心 gate 的 policy 构建期，执行期不感知套件——**安全边界不插件化**。

---

## 七、语义层绑定要求

`context_defaults.semantic_model: required`，`semantic.require: required`。四动作（绑定 / 圈定 / pin / 提案）：

- **绑定**：`semantic.layer: mysql_prod`（语义层实例 id），会话创建时由 binder 绑定，头部常驻**语义层 chip（紫）**显示数据源 + 表白名单规模（如 `🧬 语义层：mysql_prod · 42表白名单 ✓`）。
- **圈定**：`semantic.scope` 限定指标范围（`valid_gmv`、`active_users`、`order_count`）与业务域标签（`交易`）。SQL 中出现的每张表都必须在白名单内，越界表 = `sql.validate` error。
- **pin**：`pin.policy: latest_published` → 取最新已发布指标版本，并在**会话开始时定格**，保证同会话内多次引用同一指标口径一致（避免前后漂移）。需要固定版本时改 `policy: fixed` 并填 `pin.version`。
- **提案**：`proposals: []` → 用户 ✏️ 纠错产生的语义提案进待审队列，经人审发布（`status=published, version+1`）后才生效；**草稿不进入检索**，套件也**不直接修改权威源**。

**消费模式** `metric_first`：问数把语义层当作**精准口径源**（单发 SQL + 引用）；对照 `db-analysis` 的 `dataset_first`（把语义层当作多步一致性约束）。

**六步语义使用链（单发精准）**：① `SemanticRetriever` 双路召回 → ② 按 `metadata.id` 回结构化库加载权威定义 → ③ 组装 prompt（指标表达式 + 默认过滤 + join + 白名单）→ NL2SQL → ④ 执行层护栏落地（只读 SELECT、超时/行数、只读从库、行级权限）→ ⑤ 引用溯源 chips → ⑥ 👍 沉淀样例 / ✏️ 纠错待审。

**存储分工**（核心侧）：指标/规则/血缘/枚举/版本/owner → 结构化库（**权威源**）；描述/同义词/样例检索文本 → KB 托管空间（**派生索引**，chunk 带指针 `metadata{id,type,target,version}`）。故召回文本只是指针，真相必须按 id 回源。

**降级**：语义层未就绪时 binder fail-soft 降级为 `DBSummary` 表摘要注入，并在回答开头**标注水位线**（无指标口径/默认过滤/样例保证，结果需人工复核）；只读、超时、行数、行级权限、只读从库等**安全护栏照常落地**——降级的只是口径保证，不是安全边界。

---

## 八、安装与启用

**P0（官方内置，随仓库出货）**

1. 套件包已置于 `assets/suites/db-query/`，loader 扫描该目录解析 `suite.yaml`，registry 记录"装没装、启没启用、版本"（存储即包本身，无独立 manifest 存储）。
2. REST：`GET /suites` 列出（返回版本/状态/推荐问题）；`POST /suites/db-query/enable` 启用；`POST /suites/db-query/disable` 停用。
3. 启用后首页出现「🔍 智能取数」场景 Tab 与推荐问题（由 registry 渲染）；停用即从首页移除，**进行中对话保留 pin 版本直至结束**。
4. 会话创建时 binder 产出：`sop` 注入 system prompt、`tools.allow` 与核心 gate 求交、语义层绑定、产物渲染器注册、`approval_overrides` 合并进 policy。

**P1（企业自发布）**：套件管理页 zip 上传（≤50MB，根目录一个 `suite.yaml` + `skills/`），启用/停用按**工作空间（实例）级**生效。

**校验策略**：必填字段存在 + 类型粗检 + 缺省值补全，**fail-soft**（坏字段跳过并告警），不引入 jsonschema 依赖。本地自检：

```bash
cd <repo> && python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('assets/suites/db-query/**/*.yaml',recursive=True)]; print('YAML OK')"
```

---

## 九、版本与 pin

- **对话 pin**：对话创建时写 `ext_info.suite = db-query@1.0.0`，timeline 记套件版本；切换套件 = 新轮 `ext_info` + 一条「套件切换」timeline 事件，**历史不丢**、工具与策略即时生效。
- **升级不漂移**：套件升级仅影响**新对话**；历史会话保留原 pin 版本，审计可回答"这次结论是哪个套件版本跑出来的"。会话内升级为显式动作（P1）。
- **指标版本 pin**：`latest_published` 在会话开始时定格；跨会话可能取到新版本，引用溯源 chips 始终显示实际所用版本（如「指标 有效订单GMV **v2**」）。
- **语义版本约定**：`version` 遵循 semver——新增技能/命令/样例为 minor，manifest 字段语义变更或口径不兼容为 major。

---

## 十、与核心的边界（套件只声明，核心来执行）

**进套件的（声明式载荷）**：SOP/playbook、工具白名单、默认绑定、产物声明、审批 overrides（仅加严）、推荐问题与路由词、内含 skills 与 few_shots、编排策略（`execution`）。

**留在核心的（不进套件、不按场景分）**：

| 核心能力 | 为什么不能插件化 |
|---|---|
| ReAct 循环与 planner | 一个 agent 运行时；三场景不 fork 三份引擎 |
| 审批 gate 的**执行** | enforcement 点；套件只声明规则，gate 统一执行 |
| 语义层与 `SemanticRetriever` | 权威源存储与检索是地基，非场景私有 |
| 渲染器注册表 | 产物卡 UI schema 化，**不允许套件带任意前端代码** |
| 会话/记忆、引用溯源、点赞自进化闭环 | 跨场景共用，fork 会导致溯源与评测各一份 |
| 沙箱 | 安全边界 |

**反向提醒**：不要为三场景建三个 agent——那会把记忆、评测、护栏、溯源各 fork 一份，套件化就白做了。

---

## 十一、评测

推荐问题 + `few_shots/verified-queries.yaml`（8 条 Verified Q→SQL，累计 `use_count` 712）即本套件的 **eval set**，覆盖：单指标取数、维度拆分、环比（条件聚合）、Top-N + join 血缘、派生指标（客单价）、明细导出 + 脱敏、时间序列（DAU）、占比（口径收窄）。评测按套件组织，回归时校验生成 SQL 是否注入了 `status IN (1,2,3)` / `is_deleted = 0` / `tenant_id = :current_tenant` 三类过滤。
