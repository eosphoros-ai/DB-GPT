---
name: nl2sql-precision
version: 1.0.0
description: Precise NL2SQL generation with validation-driven self-correction. Use after semantic-linking has provided authoritative context (metric expression, default filters, join paths, table whitelist, column enums) to generate one correct, replayable, read-only SQL statement; also handles automatic rewrite when sql.validate reports errors.
name_en: NL2SQL Precision
name_zh: 精准 NL2SQL
description_en: Precise NL2SQL generation with validation-driven self-correction. Turns natural-language questions into one replayable read-only SQL under authoritative semantic constraints.
description_zh: 精准 NL2SQL 生成与校验自纠技能。当已拿到语义层权威口径（指标表达式、默认过滤、join 路径、表白名单、字段枚举）后需要生成一条口径正确、可复跑的只读 SQL 时使用；也用于 SQL 校验失败后的自动纠错重写。触发词：生成SQL、写SQL、nl2sql、取数、查一下、SQL校验、口径注入、可复跑、自纠、重写SQL。
user-invocable: true
argument-hint: Natural-language question (e.g., "last month East China valid GMV by channel with MoM")
argument-hint-en: Natural-language question (e.g., "last month East China valid GMV by channel with MoM")
argument-hint-zh: 自然语言问句（如"上月华东有效GMV按渠道拆分含环比"）
---

# 精准 NL2SQL (NL2SQL Precision)

## 技能目标

在语义层权威口径的约束下，把自然语言问数转换为**一条**口径正确、护栏齐备、可复跑的只读 SQL，并通过 `sql.validate` 自纠闭环保证可执行。

与通用 NL2SQL 的根本区别：**不让模型自由发挥选表选字段选口径**，而是把口径、过滤、join、白名单全部作为硬约束喂进去，模型只负责"把已确定的口径翻译成 SQL 语法"。

## 核心工作流程

1. **确认口径上下文已齐备（前置检查）**
   - 检查是否已从 `semantic-linking` 拿到四要素：**指标表达式**、**默认过滤**、**join 路径**、**表白名单**；外加**字段枚举**与**规则护栏**（`soft_delete_filter` / `row_level_security` / `timeout` / `max_rows`）。
   - 缺任一要素 → **停止生成**，回到 `semantic-linking` 补齐或向用户澄清。禁止"合理假设"后继续。

2. **组装 NL2SQL prompt（`nl2sql`）**
   - 调用 `nl2sql`，按以下结构组织上下文（顺序即优先级）：
     1. **用户问题**原句 + 已解析的时间窗（如"上个月"→ `2026-09-01` ~ `2026-10-01`，环比期 → `2026-08-01` ~ `2026-09-01`）。
     2. **指标定义**：`name` / `version` / `expression` / `table` / `time_column` / `time_grain`。
     3. **默认过滤（必须注入）**：指标级 `default_filters` + 规则级 `soft_delete_filter` + 行级权限 `row_level_security`。
     4. **join 路径**：仅允许使用语义层给出的 join key；无路径则单表查询并说明局限。
     5. **表白名单**：明确"只能使用以下表"，白名单外表名视为错误。
     6. **字段枚举**：把口语维度值映射到精确枚举值（"华东区"→ `region = '华东'`）。
     7. **few-shot 样例**：`semantic.get_examples` 命中的 1~3 条 Verified Q→SQL。
     8. **输出要求**：单条 SELECT、带口径来源注释、可复跑、含 `ORDER BY` 与合理 `LIMIT`。
   - 拿到：候选 SQL 字符串。

3. **校验（`sql.validate`）**
   - 调用 `sql.validate(sql="<候选>", rules="<guardrails.get_rules 结果>", whitelist=["orders","order_items"])`。
   - 校验项：语法可解析、表都在白名单内、**只读**（无 DML/DDL）、默认过滤已注入、行级权限已注入、join 与语义层一致、时间过滤存在（避免全表扫描）。
   - 拿到：`{errors: [...], warnings: [...], est_scan_gb: <数值>, est_scan_rows: <数值>}`。

4. **自纠重写（最多 2 轮）**
   - 有 `errors` → 把 error 文本**回灌 prompt**（"上次生成存在以下问题，请修正后重新输出完整 SQL"），重新调 `nl2sql`，再 `sql.validate`。
   - 有 `warnings`（如"环比建议用条件聚合避免两次扫描"）→ 择优采纳，不强制。
   - **2 轮后仍有 error → 停止重试**，向用户输出失败原因 + 已组装的口径上下文，请求澄清或人工介入。**绝不**把校验不过的 SQL 交给 `sql_execute`。

5. **产出 SQL 卡（可复跑 + 口径注释）**
   - 最终 SQL 必须以注释标明每段过滤的**来源**，让用户与审计都能追溯：
     - `-- 指标 met_007 v2「有效订单GMV」= SUM(order_amount)`
     - `-- 指标默认过滤`（`status IN (1,2,3)`）
     - `-- 规则护栏自动注入`（`is_deleted = 0`）
     - `-- 行级权限（执行层注入，不可移除）`（`tenant_id = :current_tenant`）
   - 参数化占位符（如 `:current_tenant`）须说明取值来源，保证用户复制后可复跑。

6. **移交执行与溯源**
   - 交 `readonly-guardrails` 技能执行（含成本预估与审批判定）。
   - 记录本次使用的指标 id/version、命中样例 id、注入的规则项，供引用溯源 chips 渲染。

## 完整流程示例

```
输入（来自 semantic-linking）：
  metric met_007 v2: expression="SUM(orders.order_amount)", table=orders,
                     default_filters=["status IN (1,2,3)"], time_column=paid_at
  enums: region=[华东,...], channel=[APP,H5,小程序,PC]
  rules: soft_delete_filter="is_deleted = 0",
         row_level_security="tenant_id = :current_tenant"
  whitelist: [orders, order_items]
  few-shot: ex_012（各区域GMV含环比）
问题：「上个月华东区的有效GMV是多少？按渠道拆一下，看看环比」（当前 2026-10-22）

Step 2: nl2sql(prompt=<问题 + 指标 + 默认过滤 + join + 白名单 + 枚举 + ex_012>)
  → 候选 SQL（第 1 轮）

Step 3: sql.validate(sql=<候选>, rules=<上述>, whitelist=["orders","order_items"])
  → errors:   ["缺少规则护栏 is_deleted = 0"]
    warnings: ["环比建议用条件聚合避免两次全表扫描"]
    est_scan_gb: 2.4, est_scan_rows: 8_600_000

Step 4: 把 error 回灌 → nl2sql 重生成（第 2 轮）→ sql.validate 复校
  → errors: [], warnings: [], est_scan_gb: 1.8   ✅ 通过

Step 5: 产出 SQL 卡
  SELECT channel,
         SUM(CASE WHEN paid_at >= '2026-09-01' AND paid_at < '2026-10-01'
                  THEN order_amount END) AS valid_gmv_cur,
         SUM(CASE WHEN paid_at >= '2026-08-01' AND paid_at < '2026-09-01'
                  THEN order_amount END) AS valid_gmv_prev,
         ROUND((SUM(CASE WHEN paid_at >= '2026-09-01' AND paid_at < '2026-10-01' THEN order_amount END)
              - SUM(CASE WHEN paid_at >= '2026-08-01' AND paid_at < '2026-09-01' THEN order_amount END))
              / NULLIF(SUM(CASE WHEN paid_at >= '2026-08-01' AND paid_at < '2026-09-01' THEN order_amount END), 0)
              * 100, 2) AS mom_pct
  FROM orders
  WHERE region = '华东'                 -- 口语「华东区」→ 枚举精确值
    AND status IN (1,2,3)               -- 指标 met_007 默认过滤
    AND is_deleted = 0                  -- 规则护栏自动注入
    AND tenant_id = :current_tenant     -- 行级权限（执行层注入，不可移除）
    AND paid_at >= '2026-08-01' AND paid_at < '2026-10-01'   -- 覆盖当期+环比期，命中索引
  GROUP BY channel
  ORDER BY valid_gmv_cur DESC;

Step 6: 移交 readonly-guardrails 执行；记录引用 = met_007@v2 / ex_012 / 3 条注入规则
```

## 注意事项

- **一次一条 SQL**：问数场景是"单发精准"，不做多步取数管线（多步一致性属 `db-analysis` 套件）。用户要多个指标时优先合并进一条 SQL（条件聚合），确实无法合并再分次并说明。
- **绝不裸 prompt 猜 SQL**：没有语义层口径就生成 SQL 是本技能的头号禁忌。语义层未就绪时走降级路径（DBSummary 摘要）并**显式标注水位线**，提示结果需人工复核。
- **默认过滤不可省略**：即使用户没提"有效订单""未删除"，`default_filters` 与 `soft_delete_filter` 也必须注入。用户明确要求去掉时：行级权限**不可协商**；软删除/指标默认过滤须拒绝并解释口径风险。
- **环比/同比用条件聚合**：优先 `SUM(CASE WHEN ...)` 单次扫描，而非两条 SQL 或自连接，降低扫描成本（直接影响审批是否被触发）。
- **除零保护**：环比/占比类计算一律用 `NULLIF(denominator, 0)`。
- **时间过滤必带**：缺时间范围的聚合会被 `sql.validate` 判 warning、并可能命中 `without_time_filter` 审批 override；主动收窄时间窗。
- **枚举精确匹配**：禁用 `LIKE '%华东%'`（串数据 + 丢索引）。枚举值缺失时先 `metadata.get_table` 补查，不要猜。
- **不生成非 SELECT**：任何 DML/DDL 请求直接拒绝并引导到 `db-ops` 套件；`tools.deny: [ddl, shell]` 是声明，核心 gate 是执行，不要试探绕过。
- **版本 pin 一致性**：同会话内同一指标须复用开始时定格的版本，避免前后口径漂移。
