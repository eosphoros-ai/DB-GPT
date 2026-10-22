# 智能分析套件 · db-analysis

> DB-GPT 官方场景套件（Scenario Suite）· `db-analysis@1.0.0` · execution: `react`
> 三官方套件之二：`db-query`（智能取数）· **`db-analysis`（智能分析）** · `db-ops`（智能运维）
> 设计依据：[`docs/design/data-agent-product-design.md`](../../../docs/design/data-agent-product-design.md) §4.1 / §5.1 / §7.3、[`docs/design/scenario-suite-impl-plan.md`](../../../docs/design/scenario-suite-impl-plan.md) §一

---

## 1. 定位

**一个 ReAct agent + 三个套件**：套件是"会话级声明式配置束"，agent 是执行器。**套件只声明，核心来执行**。

`db-analysis` 面向企业业务库的**图文数据分析**场景：用户用一句自然语言（"分析本月华东区销售下滑的归因，出图文报告"）驱动一条完整分析链路——

```
理解需求 → 圈定数据集 → 多步取数 → 图表卡 → 结论提炼卡 → 报告卡（HTML/PDF，含引用 chips）
```

它与 `db-query` 的本质差别不在工具多少，而在**语义层的用法**：

| | db-query（问数） | db-analysis（分析） |
|---|---|---|
| 语义层角色 | 精准口径源（单发 SQL + 引用溯源） | **多步一致性约束**（数据集圈定 + 跨步口径统一 + 指标版本 pin） |
| 默认绑定 | 语义模型 | **数据集**（语义层表白名单 + 血缘 join 路径 + 语义模型） |
| 交付物 | 结果集 + 可复跑 SQL | **图文分析报告**（report + charts） |
| 典型风险 | 口径选错、大扫描 | **跨步口径漂移**（同一指标不同算法）、结论臆测、图多结论少 |
| 共用机制 | 引用溯源 chips、👍 沉淀样例 / ✏️ 纠错进待审 | 同左 |

## 2. 能力清单

- **数据集圈定**：从语义层取表白名单与血缘 join 路径固化为数据集卡；模型**不从全量表选表**。
- **多步取数与口径一致**：每步 `nl2sql` 携带 `dataset_id` + `metric_refs`（含 pin 版本），默认过滤与时间粒度统一注入。
- **图表自动匹配**：柱/线/饼/散点/堆叠/双轴按数据形态选型，标题结论化、注脚带口径。
- **归因分析**：维度贡献度拆解（含闭合校验）、环比同比、量价分解、结构效应分离、异动起点定位、假异动排除。
- **图文报告**：固定章节骨架装配 + 引用 chips（指标@版本 / 表与 join / SQL 步骤 / 命中样例）+ HTML/PDF 导出与分享。
- **自进化闭环**：报告 👍 沉淀为 verified 样例（`use_count`+1）；✏️ 纠错生成语义提案进**待审队列**（不直改权威源，人审发布后 version+1，历史会话仍 pin 旧版本）。
- **代价与审批意识**：高代价扫描、超大数据集、大批量导出、外发分享均加严为 `confirm`（仅可加严）。

## 3. 包内结构

```
assets/suites/db-analysis/
├── suite.yaml                          # manifest（loader 入口，字段名即契约）
├── README.md                           # 本文件
├── prompts/
│   └── analysis-playbook.md            # SOP，注入 system prompt
├── skills/
│   ├── dataset-scoping/SKILL.md        # 数据集圈定（表白名单 + 血缘 join）
│   ├── multi-step-analysis/SKILL.md    # 多步取数与跨步口径一致（版本 pin）
│   ├── chart-advisor/SKILL.md          # 图表自动匹配与 option 容错
│   ├── attribution-analysis/SKILL.md   # 归因（贡献度/环比同比/量价/异动定位）
│   └── report-generation/SKILL.md      # 图文报告（结论提炼/引用 chips/导出）
├── templates/
│   └── report-template.md              # 报告章节骨架（report_export 的 template 入参）
└── few_shots/
    └── verified-analyses.yaml          # 6 条已验证分析样例（few-shot + eval set）
```

## 4. 内含 skills

| 技能 | 命令 | 职责 | 主要工具 |
|---|---|---|---|
| `dataset-scoping` | `/dataset` | 语义召回 → 回源 join → 裁剪表清单 → 固化数据集卡 | `semantic_search`、`schema_link`、`dataset_scope` |
| `multi-step-analysis` | `/analyze` | 计划拆解 → 逐步 nl2sql+sql_execute → 跨步一致性自检 | `semantic_search`、`nl2sql`、`sql_execute`、`chart`、`export_csv` |
| `chart-advisor` | `/chart` | 形态识别 → 选型 → 维度度量映射 → option JSON 容错自修 | `chart` |
| `attribution-analysis` | `/attribute` | 假异动排除 → 贡献度拆解与闭合 → 量价/结构分解 → 异动定位 → 结论卡 | `semantic_search`、`nl2sql`、`sql_execute`、`chart` |
| `report-generation` | `/report` | 素材盘点 → 摘要提炼 → 章节装配 → 引用 chips → HTML/PDF 导出 | `report_export`、`export_csv`、`chart` |

技能格式为仓库既有 `SKILL.md`（frontmatter 仅 `name` + `description`），走现有 skill registry 与 zip 上传通道；`skills` 块在 manifest 中仅作索引。

## 5. 快捷命令

| 命令 | 作用 | 示例 |
|---|---|---|
| `/analyze` | 跑完整分析链路，默认产出图文报告 | `/analyze 本月华东区销售下滑归因，出图文报告` |
| `/dataset` | 圈定或查看当前数据集（表清单 + join + 口径） | `/dataset 交易域，华东区，近 90 天` |
| `/chart` | 对当前结果集出图（自动选型，可显式指定） | `/chart 按周 valid_gmv 折线，series=渠道` |
| `/report` | 汇总图表与结论导出报告（HTML/PDF） | `/report html 分享链接` |
| `/attribute` | 归因：贡献度拆解 + 环比同比 + 异动定位 | `/attribute 本月华东区 valid_gmv 下滑，拆渠道与品类` |

## 6. manifest 关键值（`suite.yaml`）

| 字段 | 值 | 说明 |
|---|---|---|
| `kind` / `name` / `version` | `scenario-suite` / `db-analysis` / `1.0.0` | slug 全局唯一；对话创建时 pin `db-analysis@1.0.0` |
| `scenario_id` / `icon` / `display` | `analysis` / 📊 / 智能分析 | 首页场景 Tab 渲染数据源 |
| `execution` | `react` | P0 仅 react；报告确定性后处理留 P1 flow（见 §11） |
| `sop` | `prompts/analysis-playbook.md` | 注入 system prompt 的行事规程 |
| `tools.allow` | `semantic_search, schema_link, nl2sql, sql_execute, dataset_scope, chart, report_export, export_csv` | 问数全集 + 分析三件套 |
| `tools.deny` | `ddl, shell` | 分析场景永不需要的破坏性能力 |
| `context_defaults` | `semantic_model: required`、`dataset: required`、`datasource: session`、`time_window: session` | 数据集是**必需**绑定 |
| `semantic.pin` | `policy: pin`、`versions: {valid_gmv: v2, paid_order_cnt: v1, aov: v1, refund_rate: v1}` | 会话级 pin，见 §9 |
| `semantic.consumption` | `metric_first` | 每步取数仍以指标定义为口径源；dataset 是范围约束 |
| `artifacts` | `dataset_card, chart, conclusion_card, report, citation` | 引用核心渲染器注册表，不自带 UI 代码 |
| `approval_overrides` | 高代价扫描 / 超大行数 / 无时间过滤 / 数据集 > 40 表 / 外发分享 / 大批量导出 → `confirm` | **仅可加严**，合并顺序 core deny > suite > core default |
| `routing.keywords` | 分析、归因、报告、趋势、对比、占比、下滑、洞察、可视化、拆解、贡献度、异动、复盘 | `specificity: 0.85`（高于 db-query 的 0.8） |
| `output_contract` | `report+charts` | 完成标准：报告卡 + 支撑图表 + 引用 chips |
| `report_formats` / `templates.report` | `[markdown, html, pdf]` / `templates/report-template.md` | html 为默认分享形态 |

## 7. 数据集与语义层绑定要求（启用前必读）

1. **语义层实例必须存在**（`semantic.layer: mysql_prod`）：包含元数据目录、语义标注（`published` 态）、指标口径（版本化）、样例库、血缘图谱、规则护栏六类内容。草稿态语义条目**不进入检索**。
2. **表白名单**：分析用到的表必须在语义层白名单内且有语义标注；否则 `dataset_scope` 只能基于 DBSummary 表摘要降级圈定，报告需标注水位线且结论置信度下调一档。
3. **血缘 join 路径**：需登记 join key 与基数（1:N / N:1）。缺失 join 路径的表无法进入同一数据集（避免模型即兴写 join）。
4. **指标口径**：至少提供 `valid_gmv`（或企业等价 GMV 指标）与订单量、客单价类指标，并带版本号、默认过滤、时间粒度、owner、状态。
5. **默认过滤与规则**：软删除、测试单剔除、订单状态、行级权限、只读从库、超时与行数上限——由规则护栏声明，数据集圈定时一次注入，各步不重复。
6. **数据源**：`datasource: session`，会话创建时确定并 pin；执行一律走只读从库。
7. **降级策略**：语义层未就绪时 binder fail-soft（DBSummary 摘要注入 + 水位线标注），**不报错、不阻塞**，但报告必须显式声明口径未经语义层确认。

## 8. 报告形态

- **章节骨架固定**（`templates/report-template.md`）：标题与元信息表 → 一、摘要 → 二、数据集与口径说明 → 三、多维度图表分析 → 四、归因结论（含贡献度分解、待验证假设、可信度排除）→ 五、建议与后续动作 → 六、引用溯源附录。
- **产物卡**：`dataset_card`（表清单白名单态 + join 路径）、`chart`（ECharts option，核心渲染器出图）、`conclusion_card`（结论 → 证据 → 口径 → 置信度 → 建议）、`report`（HTML/PDF + 分享链接）、`citation`（引用 chips）。
- **引用 chips 三类必备**：指标版本（`valid_gmv@v2`）、数据来源（表 + join + 只读从库 + 行级权限）、执行痕迹（SQL 步骤号 + 命中样例 id）。
- **分享与合规**：内部链接默认可分享；`share_scope: external` 触发审批 `confirm`，导出前完成脱敏并标注密级与可见范围。
- **右栏查看器**：数据集表清单 + join 路径 + 报告预览。

## 9. 版本 pin：分析场景为何必须 pin 指标版本

`db-query` 用 `pin.policy: latest_published`（单发 SQL，取最新口径最合理）；`db-analysis` 用 **`pin.policy: pin` + `versions` 映射**，原因：

1. **跨步一致性**：一次分析会产出 5~8 步 SQL、3~6 张图与多段结论。若各步各自解析"最新口径"，中途发布新版本会造成"同一指标两种算法"，环比对不上、贡献度不闭合、报告自相矛盾。
2. **结论可复现**：报告是决策依据，读者与审计需要能回答"这个结论是哪个口径算出来的"。pin 后报告全文引用同一版本，任何时候复跑结果一致。
3. **升级不破坏历史**：会话 pin `db-analysis@1.0.0` 与 `valid_gmv@v2`；指标升级只影响**新会话**，历史报告与历史对话不被追溯改写。需要新口径时显式新开会话或走"会话内升级"动作（P1）。
4. **纠错走待审而非直改**：报告 ✏️ 纠错生成语义提案进待审队列，人审发布后 `version+1`；本会话仍用旧版本出报告，并如实告知"提案已提交、口径未变"。
5. **量价/贡献度分解的算术前提**：`ΔGMV = 量效应 + 价效应`、`Σ 子项贡献度 = 100%` 这类校验只有在各步同版本时才成立（样例中误差 > 1% 即要求复核版本）。

## 10. 与核心的边界（什么在套件、什么在核心）

| 在套件内（声明式载荷） | 在核心（执行器，不进套件） |
|---|---|
| SOP / playbook（`prompts/analysis-playbook.md`） | ReAct 循环与 planner |
| 工具白名单 + deny（`tools`） | 审批 gate 的**执行**、沙箱 |
| 默认绑定（数据集 / 语义层 / 数据源） | 语义层存储与 SemanticRetriever |
| 产物声明（`artifacts`，引用渲染器） | 渲染器注册表（dataset_card/chart/report/citation） |
| 审批 overrides（**仅加严**） | 策略合并 `merge_suite_overrides`（core deny > suite > core default） |
| 推荐问题 + 路由词 | 首页路由评分与会话 pin / 切换（`ext_info.suite`） |
| skills / few_shots / templates | 引用溯源、点赞自进化闭环、会话与记忆 |
| 编排策略（`execution`） | AWEL flow 运行时 |

安全边界：套件**不带前端代码、不带 in-process 任意代码**；自带工具一律走 MCP server（本套件 `provide_mcp: []`，全部复用核心内置工具）。

## 11. 安装与启用

**P0（官方内置，随仓库出货）**

1. 套件目录已在 `assets/suites/db-analysis/`，loader 扫描 `assets/suites/*/suite.yaml` 并注册到 suite registry（记录"装没装、启没启用、版本"）。
2. 通过 REST 启用：`POST /api/v1/suites/db-analysis/enable`（列表：`GET /api/v1/suites`；停用：`POST /api/v1/suites/db-analysis/disable`）。
3. 启用后首页出现「📊 智能分析」场景 Tab 与本套件的推荐问题；停用即从首页移除（进行中对话保留 pin 版本直至结束）。
4. 新建对话时选择该场景（或在 composer 输入分析类问句由路由命中），对话创建即写入 `ext_info.suite = db-analysis@1.0.0`，binder 完成：SOP 注入 → 工具 allowlist 求交 → 数据集/语义层绑定 → 审批 overrides 合并（仅加严）→ 产物渲染器挂载。
5. 前置条件：语义层 `mysql_prod` 已发布指标与血缘、数据源已连接（否则按本节第 7 条降级运行）。

**P1（管理页 / zip 上传）**：套件管理页安装·启用·升级·卸载，按工作空间（实例）级生效；企业可基于本套件派生行业套件（如"财报分析专家" = db-analysis + 财报语义模型 + 年报解析 skill）。

**自检（内容合法性）**

```bash
cd <repo-root>
python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('assets/suites/db-analysis/**/*.yaml',recursive=True)]; print('YAML OK')"
```

## 12. P1 flow 化计划（报告生成的确定性后处理）

`execution: react` 下，报告装配靠 SOP 约束 ReAct 逐步完成——够用但不确定：章节可能漏、图表绑定可能错、引用可能缺。P1 将报告后处理锚定为 AWEL flow：

```yaml
# P1 变更示意（其余声明不变）
execution: flow
flow: analysis-report-flow      # 引用现有 chat_flow / AWEL DAG
```

- **flow 负责确定性部分**：素材完整性校验（数据集/口径/图表/结论齐备）→ 章节绑定与顺序校验 → 引用 chips 装配与去重 → 数字一致性校验（摘要 vs 正文 vs 注脚）→ HTML 渲染 → PDF 导出 → 分享链接与脱敏检查 → 反馈回流（👍/✏️）。
- **技能职责收敛为内容生产**：`multi-step-analysis` / `attribution-analysis` / `chart-advisor` / `report-generation` 仍负责取数、归因、选型与文字撰写，不再负责装配顺序与校验。
- **引擎仍是一个**：flow 只是 `execution` 的另一种取值，不新建 agent、不 fork 记忆与溯源（设计 §5.8「唯一不能完全声明化的是控制流形态」）。
- **兼容性**：manifest 其余字段不变，历史对话仍 pin `db-analysis@1.0.0`（react）；flow 版本以 `db-analysis@1.1.0` 发布，升级只影响新对话。
- **其他 P1 项**：套件详情页 `/commands` 展示、推荐问题可编辑、会话内升级动作、报告分享页与定时周期化（周报/月报接 Scheduled Tasks）。

## 13. 版本记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0.0 | 2026-10 | 首个官方版本：manifest + playbook + 5 skills + 报告模板 + 6 条 verified 样例；`execution: react`；`pin.policy: pin`（valid_gmv@v2 等 4 个指标） |
