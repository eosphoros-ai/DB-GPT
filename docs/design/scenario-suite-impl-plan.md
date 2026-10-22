# 场景套件（Plugin）落地改造方案

> v1.0 · 2026-10-22 · 配套：`data-agent-product-design.md` §4/§5、`data-agent-product-mockup.html`
> 结论先行：**manifest 不是独立 schema 系统，而是套件包的入口文件约定**（如 SKILL.md 之于技能）。必做代码仅 loader/registry/binder/router+pin 四块薄逻辑；codegen、校验服务、manifest 编辑 UI、市场均不做（后两者 P1/P2）。

---

## 一、manifest 的定位：套件内容本身，不是新东西

- 套件包 = 目录或 zip，根目录一个 `suite.yaml`（manifest）+ `skills/`（现有 SKILL.md 格式）+ 可选 `prompts/`、`flows/` 引用。
- manifest 只做两件事：① **索引包内内容**（skills 列表、sop 文件、flow 引用）；② **声明政策**（工具白名单、默认绑定、审批加严、产物、路由词、编排策略）。
- 存储即包本身；registry 只记"装没装、启没启用、版本"。无独立 manifest 存储、无 schema codegen。
- 校验策略：必填字段存在 + 类型粗检 + 缺省值补全，fail-soft（坏字段跳过并告警），不引入 jsonschema 依赖。
- 反例说明为何不能"零 manifest"：审批加严/默认绑定/编排策略若无统一落点，只能塞进各 SKILL.md frontmatter → manifest 被打散、治理口子失守。

### suite.yaml 最小约定（P0 字段）

```yaml
kind: scenario-suite
name: db-query            # slug，唯一
display: 智能取数
version: 1.0.0
execution: react          # react | flow(P1)；flow 时填 flow: <flow_id>
sop: prompts/playbook.md  # 包内相对路径
tools:
  allow: [semantic_search, schema_link, nl2sql, sql_execute, export_csv]
  deny: [ddl, shell]
context_defaults:
  semantic_layer: required   # required | optional | none
  datasource: session        # 会话选择
approval_overrides:          # 仅可加严，合并顺序 core deny > suite > core default
  - match: {tool: sql_execute, est_scan_gb: ">100"}
    action: confirm
artifacts: [sql_card, result_table, citation]
routing:
  keywords: [查, 统计, 导出, GMV, top]
recommended_questions:
  - {text: 上个月华东区有效GMV, hint: 指标 v2 口径 + 默认过滤自动注入}
```

---

## 二、现状盘点（复用点，不新造）

| 能力 | 现有落点 | 套件化复用方式 |
|---|---|---|
| 技能加载 | pi `tool_bridge._skill_tools`（load_skill 等）、SKILL.md+zip 上传通道、`web/pages/construct/skills` | 套件 `skills/` 直接走现有 skill registry；上传通道复用 |
| 工具 gate | `packages/dbgpt-core/src/dbgpt/agent/expand/actions/tool_action.py`（run_tool 闸） | binder 产出的 allowlist 交 gate 执行 |
| 审批策略 | `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/approval.py`（ToolRiskPolicy/ApprovalCenter/make_approval_gate） | suite approval_overrides 在会话开始合并进 policy（仅加严） |
| 会话/场景 | `newDialogue(chat_mode/scene)`、`ext_info` 按请求覆盖（harness_engine 先例） | suite pin 走 `ext_info.suite`；切换=新轮 ext_info+事件 |
| 编排 | AWEL DAG（`core/awel/`）、chat_flow | `execution: flow` 时引用现有 flow（P1） |
| 语义层 | 设计已定（SemanticRetriever/白名单/指标），代码 P0 并行推进 | binder 绑定 semantic_layer id；未就绪时 fail-soft 降级为 DBSummary |
| 前端 | 首页 Explore、`web/pages/chat/*`、`new-components/chat/*`（ApprovalDock 等） | 场景 Tab/前缀 chip/套件 chip 从 registry 渲染 |

---

## 三、P0 改造任务（文件级）

| # | 任务 | 落点 | 估行 | 验收 |
|---|---|---|---|---|
| T1 | 套件包约定 + 三个官方套件入库 ✅ 2026-10-22 | `assets/suites/{db-query,db-analysis,db-ops}/`（suite.yaml+skills/+prompts/） | ~300（内容） | 三包可被 loader 解析；skills 为合法 SKILL.md |
| T2 | loader + registry + REST ✅ 2026-10-22 | 新增 `packages/dbgpt-serve/src/dbgpt_serve/plugins/{loader,registry,api}.py` + `models/` + `service/` + `serve.py` | ~500 | GET /suites、POST /suites/{id}/enable、disable；返回版本/状态/推荐问题 |
| T3 | binder：套件→会话配置 ✅ 2026-10-22 | `dbgpt-app/openapi/api_v1/suite_binder.py`（新增）+ 挂接 `agentic_data_api.py`（dbgpt 引擎：SOP 前置 + gate 外层组合）与 `harness_pi_stream.py`（pi 引擎：per-conv 绑定 + loopback tool-run 前置检查） | ~250 | 会话配置含 sop 注入/allowlist 求交/绑定/渲染器；缺语义层时降级不报错 |
| T4 | 审批合并（仅加严） | `approval.py` 增 `merge_suite_overrides(policy, suite)` | ~80 | suite 放宽核心 deny 的被拒；加严生效并有单测 |
| T5 | 首页路由（关键词评分） | binder 旁 `router.py`：suite routing.keywords 评分，平局交 LLM 意图 | ~120 | 三类问句路由准确率自测集 ≥90% |
| T6 | pin 与切换 | 对话创建写 `ext_info.suite=suite@version`；切换端点写新轮 ext_info + timeline 事件 | ~100 | 历史轮保留旧 pin；切换后工具/策略即时生效 |
| T7 | 前端：Tab/前缀 chip/套件 chip/侧栏标签 | 首页 Explore、chat 头部、侧栏 ALL TASKS | ~400 | Tab 与推荐问题来自 registry；切换 chip 触发 T6；标签按 pin 渲染 |

顺序：T1→T2→T3→T4→T6→T5→T7（T5 依赖 T2 的 routing 数据）。P0 不含 `execution: flow`（解析字段保留，值仅 react）。

## 四、P1 / P2（不展开）

- P1：套件管理页（zip 上传/启用按工作空间）、详情页（/commands 来自 skills）、推荐问题可编辑、`execution: flow` 接 chat_flow、manifest 编辑 UI。
- P2：市场发布、策略合并 UI、按套件版本审计、meta-agent 生成套件。

## 五、风险与取舍

- **套件 vs 技能边界混淆**：套件=会话级配置束（含 N 技能）；技能=会话内可调用过程。UI 与文档统一此口径。
- **加严 enforcement**：合并发生在 policy 构建期，gate 执行期不感知套件 → 安全边界不插件化（§5.4）。
- **版本 pin 与升级**：对话 pin 不随套件升级漂移；升级仅影响新对话；提供"会话内升级"显式动作（P1）。
- **语义层未就绪**：binder 对 `semantic_layer: required` 做降级（DBSummary 摘要注入）并在水位线标注，避免 P0 被语义层进度阻塞。

## 六、验收清单（P0 出口）

1. 三个官方套件可安装/启用/停用，首页 Tab 与推荐问题随之增减；
2. 同一句问数在启用/停用 db-query 下工具集与审批行为可观测差异；
3. 对话 pin 套件@版本，切换套件产生 timeline 事件且历史不丢；
4. suite 试图放宽核心 deny 被拒绝（单测覆盖）；
5. 语义层缺失时取数会话降级可用（DBSummary）且不报错。
