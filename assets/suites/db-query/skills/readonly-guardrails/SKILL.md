---
name: readonly-guardrails
version: 1.0.0
description: Read-only safe execution and cost guardrails. Use after a SQL passes sql.validate and needs to run on a read replica with cost estimation, approval routing (confirm on high-cost scans), and enforcement of timeout / row-limit / row-level-security / soft-delete filters; also handles timeout, over-row-limit, and approval-rejected exceptions.
name_en: Readonly Guardrails
name_zh: 只读安全执行
description_en: Read-only safe execution and cost guardrails. Runs validated SQL on a read replica with cost estimation, approval routing, timeout / row-limit / row-level-security enforcement.
description_zh: 只读安全执行与成本护栏技能。当 SQL 通过 sql.validate 后需要在只读从库上执行、需要预估扫描成本判断是否触发审批 confirm、需要落地超时/行数上限/行级权限/软删除过滤时使用；也用于处理执行超时、超行数、审批被拒等异常。触发词：执行SQL、跑一下、只读、从库、replica、超时、行数上限、大扫描、高代价、扫描成本、审批确认、行级权限、tenant_id、护栏。
user-invocable: false
argument-hint: Validated SQL to execute on read replica (with cost/approval check)
argument-hint-en: Validated SQL to execute on read replica (with cost/approval check)
argument-hint-zh: 已校验的 SQL（在只读从库执行，含成本预估与审批判定）
---

# 只读安全执行 (Readonly Guardrails)

## 技能目标

在**执行层**（而非 prompt 层）落地问数场景的四道护栏，保证任何一次取数都是只读的、有界的、路由到从库的、带行级权限的；并在高代价扫描时把决策权交回用户（审批 dock），不擅自绕过。

关键原则：**护栏是 enforcement，不是建议。** 套件 `approval_overrides` 只做声明，核心 gate 负责执行；合并顺序 `core deny > suite > core default`，套件只能加严不能放宽。

## 核心工作流程

1. **执行前门禁复查（不信任上游）**
   - 确认 SQL 已通过 `sql.validate`（`errors` 为空）。未通过 → 退回 `nl2sql-precision`，**不得执行**。
   - 确认语句类型为单一 `SELECT`（或 `WITH ... SELECT`）。出现 `INSERT/UPDATE/DELETE/REPLACE/MERGE/TRUNCATE/DROP/ALTER/CREATE/GRANT/CALL/SET` → 直接拒绝，告知该操作属 `db-ops` 场景（套件 `tools.deny: [ddl, shell]`）。
   - 确认三类过滤均在位：指标 `default_filters`、`soft_delete_filter`（`is_deleted = 0`）、`row_level_security`（`tenant_id = :current_tenant`）。缺项 → 由执行层补注入或退回重写。

2. **成本预估与审批判定**
   - 从 `sql.validate` 结果读取 `est_scan_gb` / `est_scan_rows`，或调用 `sql_execute` 的 dry-run/预估模式获取。
   - 对照 `suite.yaml` 的 `approval_overrides` 判定：
     - `est_scan_gb > 100` → `confirm`（理由：高代价扫描）
     - `est_scan_rows > 50000000` → `confirm`（超大行数扫描）
     - `without_time_filter: true` → `confirm`（缺时间过滤的全表聚合）
   - 命中 → **停止执行**，把风险等级、预估扫描量、预估费用、预估耗时交核心审批 gate 弹 dock；同时准备替代方案（加 `LIMIT 1000` 预览 / 收窄时间窗 / 改聚合查询）。
   - 未命中（如 `est_scan_gb ≈ 1.8`）→ 走 `auto` 放行，无需打扰用户。
   - **禁止规避**：不得为了让查询"看起来便宜"而擅自拆小、加 LIMIT 绕过成本闸门（用户主动要求预览除外）。

3. **执行（`sql_execute`）**
   - 调用参数：
     ```json
     sql_execute(sql="<已校验 SQL>", mode="readonly", route="replica",
                 timeout=30, max_rows=1000,
                 params={"current_tenant": "<会话身份>"})
     ```
   - `mode="readonly"`：连接层拒绝非 SELECT。
   - `route="replica"`：路由到**只读从库**，不打生产主库。
   - `timeout`：默认 30s（取 `guardrails.get_rules` 的 `timeout_seconds`）。
   - `max_rows`：预览默认 1000 行（取 `max_rows`）；需要全量时改走 `result-export` 技能导出，而非放大预览。
   - `params`：行级权限参数由**会话身份**注入，模型无权改写或移除。
   - 拿到：`{columns, rows, row_count, elapsed_ms, executed_on: "replica", truncated: bool}`。

4. **结果卡渲染信息补齐**
   - 结果卡必须显示：**只读从库执行 · 耗时 Xms · 返回 N 行**；被 `max_rows` 截断时显式标注"已截断，导出可得全量"。
   - SQL 卡保留口径来源注释；引用溯源 chips 追加**规则**项（`is_deleted=0 · status IN(1,2,3) · tenant_id 行级`）。

5. **审批决议回灌**
   - 用户**批准** → 按原参数执行，并把记忆作用域（仅本次 / 本会话 / 始终询问）写回 gate。
   - 用户**拒绝** → 不重复弹同一审批；提供替代方案（预览 / 缩窗 / 离线导出），或按用户指示终止。
   - 用户选择"加 LIMIT 1000 预览" → 重写为预览查询，明确告知这是样本而非全量结论。

6. **异常处理**
   - **超时** → 返回已取部分（若有）+ 建议：缩小时间窗、增加维度过滤、改聚合。不静默重试。
   - **超行数** → 提示走 `/export` 导出，而非提高 `max_rows`。
   - **权限不足 / 表不在白名单** → 明确告知需在语义层扩容白名单或申请权限，不绕道查同义表。
   - **从库延迟** → 若结果与用户预期的实时数据不符，提示 replica 存在同步延迟，必要时说明数据时点。

## 完整流程示例

```
输入：已通过 sql.validate 的 SQL（华东区上月有效GMV按渠道拆分含环比）
      est_scan_gb = 1.8, est_scan_rows = 8_600_000

Step 1: 门禁复查
  → 单一 SELECT ✅ / 白名单表 orders ✅
  → status IN (1,2,3) ✅  is_deleted = 0 ✅  tenant_id = :current_tenant ✅

Step 2: 审批判定
  → est_scan_gb 1.8 < 100，est_scan_rows 8.6M < 50M，含时间过滤
  → 未命中任何 approval_overrides → auto 放行

Step 3: sql_execute(sql=<SQL>, mode="readonly", route="replica",
                    timeout=30, max_rows=1000,
                    params={"current_tenant": "t_8821"})
  → columns: [channel, valid_gmv_cur, valid_gmv_prev, mom_pct]
    rows: [[APP,742310.00,651200.00,13.99], [小程序,318450.00,296100.00,7.55],
           [H5,164200.00,178900.00,-8.22], [PC,59600.00,62300.00,-4.33]]
    row_count: 4, elapsed_ms: 46, executed_on: "replica", truncated: false

Step 4: 结果卡 → 「只读从库执行 · 46ms · 4 行」
        引用溯源 chips 追加：规则 is_deleted=0 · status IN(1,2,3) · tenant_id 行级

—— 对照：高代价场景 ——
用户追问「把这三年的订单明细全量拉出来」
Step 2': est_scan_gb ≈ 480 > 100 → 命中 approval_overrides
  → 停止执行，交审批 gate 弹 dock：
    风险等级：中风险 · 预估扫描 ~480 GB · 预估费用 ¥62.4 · 耗时 ~3min
    动作：[确认执行] [取消] [加 LIMIT 1000 预览]  记忆：[仅本次/本会话]
Step 5': 用户选「加 LIMIT 1000 预览」→ 重写预览查询，标注"样本非全量"
```

## 注意事项

- **只读铁律**：本技能只放行 `SELECT`。任何写/结构变更请求一律拒绝并引导到 `db-ops` 套件；不要试探核心 gate。
- **护栏在 SQL 里可见**：`is_deleted = 0`、`tenant_id = :current_tenant`、`status IN (1,2,3)` 必须真实出现在最终 SQL 中并带来源注释，不能只在 prompt 里"说过"。
- **行级权限不可协商**：`tenant_id` 由执行层按会话身份注入；用户要求跨租户取数时拒绝并说明需走权限变更审批（属权限变更类确认，不在问数套件范围内）。
- **审批只能加严**：套件不得把核心 deny 放宽成 auto；此类 override 会在 `merge_suite_overrides` 阶段被拒绝，不要写入 manifest。
- **不放大预览上限**：需要全量数据时用 `result-export`（`export_csv`）走导出通道（> 10 万行会触发 confirm），而不是把 `max_rows` 调到十万级撑爆对话。
- **不静默重试**：超时/失败要告知用户原因与建议，避免重复消耗从库资源。
- **降级态仍须护栏**：语义层未就绪、降级为 DBSummary 摘要时，只读、超时、行数、行级权限、只读从库**照样落地**；降级的只是口径保证，不是安全边界。
- **执行信息要留痕**：`executed_on`（replica）、`elapsed_ms`、`row_count`、`truncated` 均须回显，便于审计与用户判断数据时点。
