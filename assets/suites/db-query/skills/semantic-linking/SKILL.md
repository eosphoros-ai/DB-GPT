---
name: semantic-linking
command: /schema
version: 1.0.0
description: Semantic retrieval and authoritative definition loading. Use when mapping natural-language business terms (e.g., "valid GMV", "ARPU", "East China", "active users") to authoritative metric definitions, table schemas, column enums, and guardrail rules in the semantic layer. Also answers "what is the definition of this metric / which version / what default filters", "is this table whitelisted", "what values does this column take".
name_en: Semantic Linking
name_zh: 语义召回与口径加载
description_en: Semantic retrieval and authoritative definition loading. Use when mapping natural-language business terms to authoritative metric definitions, table schemas, column enums, and guardrail rules in the semantic layer.
description_zh: 语义召回与权威口径加载技能。当需要把用户的自然语言业务名词（如"有效GMV""客单价""华东区""活跃用户"）映射到语义层的权威指标定义、表结构、字段枚举与规则护栏时使用；也用于回答"这个指标口径是什么/哪个版本/默认过滤有哪些""这张表在不在白名单里""字段有哪些取值"。触发词：指标口径、指标定义、语义层、语义召回、schema、表结构、字段含义、枚举值、白名单、metric、版本、同义词。
user-invocable: true
argument-hint: Business term or question (e.g., "valid GMV", "orders table schema")
argument-hint-en: Business term or question (e.g., "valid GMV", "orders table schema")
argument-hint-zh: 业务名词或问句（如"有效GMV"、"orders 表结构"）
---

# 语义召回与权威口径加载 (Semantic Linking)

## 当前运行时工具契约 / Current runtime tools

本节优先于下面的目标架构示例；示例中的点号工具、双路向量检索、
规则/血缘/样例读取是设计说明，不能按示例工具名发起调用。

1. `semantic_search_metrics(query="有效GMV", limit=10)`：搜索当前库已发布指标。
2. `semantic_get_metric(metric_id=<返回的整数ID>, version=<整数版本>)`：
   回源读取已发布快照，包含 `metric_definition`、`formula`、`base_metrics`、
   `dimensions`、版本、发布时间和 `citation`。也可用精确 `metric_name`，
   与 `metric_id` 二选一。未传版本时取最新已发布版本。
3. `semantic_search_business(query="华东区", table_name="orders", limit=20)`：
   查询已发布表/字段业务释义、同义词及定义，返回目标表列与版本。
4. `semantic_get_metadata(table_name="orders", limit=20)`：
   查询同步的表字段、类型、注释、主外键标记、枚举、敏感/白名单标记。
   该工具返回元数据快照，不代表业务口径已经发布，需检查 `last_sync_at`。

工具只读且绑定当前数据库，不传 `layer`、`ds_id`、`types` 或 `top_k`。
普通 `semantic_search` 仍是知识库检索。返回为空或未发布时明确说明，
不得使用草稿或常识充当正式口径。多步取数复用返回版本；只使用定义中实际
存在的过滤、时间字段和维度。读取不等于 SQL 强校验、自动 pin 或规则执行。

Use these four tools for structured semantic-center reads. Search business terms,
load an exact published metric snapshot, inspect published aliases, then verify
the schema snapshot. Reuse the returned version and cite `citation`. Do not call
the hypothetical dotted tools below or pass their unsupported parameters.
Missing results or fields require clarification; they are not governed semantics.

## 技能目标

把用户口语中的业务名词，**精准且可溯源地**落到语义层的权威定义上，为后续 NL2SQL 提供"四要素齐备"的口径上下文（指标表达式 / 默认过滤 / join 路径 / 表白名单）。

核心信条：**向量召回只是索引，结构化库才是真相。** 召回返回的文本片段是派生 chunk，可能滞后、截断或因更换 embedding 模型而重建；任何用于拼 SQL 的口径，都必须按 `metadata.id` 回结构化库重新加载。

## 核心工作流程

1. **双路召回（`semantic_search`）**
   - 调用 `semantic_search`，参数：`query`（用户原句或抽取出的业务名词）、`types`（按类型过滤，取数场景常用 `["metric","table","column","synonym","example"]`）、`top_k`（建议 8）、`layer`（取 `suite.yaml` 的 `semantic.layer`，如 `mysql_prod`）。
   - 工具内部执行 SemanticRetriever 双路：**向量路**做语义相似 top-k 并按 `type` 过滤；**结构化路**对同义词表与指标名做精确匹配（命中即高权重）。两路按 id 去重合并排序。
   - 拿到：候选列表，每项含 `metadata{id, type, target, version}` + `text`（摘要）+ `score`。
   - **不要**把 `text` 里的公式/过滤条件当作可用口径，它只是指针。

2. **按 id 回源加载指标权威定义（`semantic.get_metric`）**
   - 对 `type == "metric"` 的候选，调用 `semantic.get_metric(id="met_007")`。
   - 拿到：`name` / `version` / `status` / `expression`（如 `SUM(orders.order_amount)`）/ `table` / `default_filters`（如 `["status IN (1,2,3)"]`）/ `time_column` / `time_grain` / `dimensions` / `join_paths`（带 join key）/ `owner`。
   - 版本选择遵循 `semantic.pin.policy`：`latest_published` 取最新已发布版本，并在会话内**定格**，避免同会话前后口径漂移。
   - `status != published`（草稿态）的指标**不得进入检索与使用**，若命中须提示用户该口径尚未发布。

3. **加载表元数据与枚举（`metadata.get_table`）**
   - 对 `type == "table"` / `"column"` 的候选，调用 `metadata.get_table(table="orders")`。
   - 拿到：列名与类型、comment、**枚举值**（`region: [华东,华南,...]`、`channel: [APP,H5,小程序,PC]`）、索引情况、`whitelisted`（是否在白名单）、`annotated`（是否已语义标注）。
   - 枚举的作用：把口语维度值精确落地（"华东区"→ `region = '华东'`），**禁止**用 `LIKE '%华东%'` 模糊匹配。
   - 表数量多、列冗长时，可再调 `schema_link` 做表列裁剪，只保留与本次问题相关的表与列，降低 prompt 噪声。

4. **取 Verified 样例做 few-shot（`semantic.get_examples`）**
   - 调用 `semantic.get_examples(question="<用户问句>", metric_ids=["met_007"], top_k=2)`。
   - 拿到：样例库中已验证的 Q→SQL 对（含 `id`、`use_count`、`verified_by`），用于 in-context few-shot。
   - 套件自带样例见 `few_shots/verified-queries.yaml`；命中样例后须在引用溯源 chips 中标注样例编号。
   - 消费模式为 `metric_first`：**命中样例优先于泛化生成**。

5. **加载规则护栏（`guardrails.get_rules`）**
   - 调用 `guardrails.get_rules(scope="mysql_prod/orders")`。
   - 拿到：`readonly`、`route`（replica 只读从库）、`soft_delete_filter`（`is_deleted = 0`）、`row_level_security`（`tenant_id = :current_tenant`）、`timeout_seconds`、`max_rows`、`table_whitelist_size`、`cost_gate`。
   - 这些规则由**执行层**强制落地，但需在此处取回并交给 `nl2sql-precision` 注入 SQL，同时在结果中说明。

6. **移交下游**
   - 把步骤 2~5 的结构化结果（而非召回摘要）打包移交 `nl2sql-precision` 技能组装 prompt。
   - 若用户只是问口径（`/metric`、`/schema` 命令），直接把权威定义以 YAML/表格形式回显给用户，并标注 `version` 与 `owner`，无需进入 SQL 生成。

## 完整流程示例

```
用户问：「上个月华东区的有效GMV是多少？按渠道拆一下」

Step 1: semantic_search(query="上个月华东区的有效GMV 按渠道拆分",
                        types=["metric","table","column","synonym","example"],
                        top_k=8, layer="mysql_prod")
  → [0] {id:"met_007", type:"metric",  target:"valid_gmv", version:2, score:0.93}
    [1] {id:"syn_042", type:"synonym", target:"met_007",   score:0.88}  "有效GMV → valid_gmv"
    [2] {id:"tbl_003", type:"table",   target:"orders",    score:0.81}
    [3] {id:"col_118", type:"column",  target:"orders.channel", score:0.77}
    [4] {id:"ex_012",  type:"example", target:"q_gmv_region_mom", score:0.74}

Step 2: semantic.get_metric(id="met_007")
  → expression: "SUM(orders.order_amount)"
    default_filters: ["status IN (1,2,3)"]
    time_column: paid_at, dimensions: [region, channel, customer_id]
    join_paths: [{left:"orders.order_id", right:"order_items.order_id", type:inner}]
    version: 2, status: published, owner: "@数据平台组"

Step 3: metadata.get_table(table="orders")
  → region enums: [华东,华南,华北,华中,西南,西北,东北]   → "华东区" 落为 region = '华东'
    channel enums: [APP,H5,小程序,PC]                    → GROUP BY channel
    whitelisted: true, annotated: true, paid_at indexed: true

Step 4: semantic.get_examples(question="上月华东有效GMV按渠道拆分",
                              metric_ids=["met_007"], top_k=2)
  → 命中 ex_012（Verified，use_count=47），作为 few-shot 注入

Step 5: guardrails.get_rules(scope="mysql_prod/orders")
  → readonly:true, route:replica, soft_delete_filter:"is_deleted = 0",
    row_level_security:"tenant_id = :current_tenant",
    timeout_seconds:30, max_rows:1000, cost_gate:{est_scan_gb_confirm:100}

Step 6: 把 Step 2~5 的结构化定义移交 nl2sql-precision 组装 prompt
  → 引用溯源 chips 需包含：指标 met_007 v2 / 表 orders 已标注 / 样例 #12 / 规则注入项
```

## 注意事项

- **绝不跳步**：没有 Step 1~2 就进入 SQL 生成属于违规（"绝不裸 prompt 猜 SQL"）。口径不明时先向用户澄清，不要凭常识假设。
- **召回文本只是指针**：`semantic_search` 的 `text` 是 KB 托管空间的派生 chunk，仅用于定位 id；权威定义只来自 `semantic.get_metric` / `metadata.get_table` 的回源结果。
- **type 过滤必开**：不加 `types` 会让向量路把规则、样例、表摘要混在一起召回，显著降低精度。
- **歧义要显式处理**：同名指标多版本（v1/v2）或多个近义指标同时命中时，列出候选（名称+版本+口径摘要+owner）请用户选择，默认倾向 `latest_published` 但须告知所用版本。
- **草稿不进检索**：`status` 非 `published` 的语义条目不可用于生成，须提示"该口径尚未发布"。
- **白名单是硬边界**：`whitelisted: false` 的表不得进入 SQL；用户坚持时告知需在语义层扩容白名单，不要绕道查同义表。
- **join 不许猜**：join key 只能来自 `join_paths`（血缘）。找不到路径时宁可只查单表并说明局限。
- **降级路径**：语义层未就绪时，binder 会 fail-soft 降级为 `DBSummary` 表摘要注入；此时本技能只做 schema linking，且必须在回答开头标注水位线（无指标口径/默认过滤/样例保证，结果需人工复核），不报错、不中断会话。
