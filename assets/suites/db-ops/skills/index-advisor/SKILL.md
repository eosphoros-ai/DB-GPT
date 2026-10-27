---
name: index-advisor
name_zh: 索引优化
command: /index
user-invocable: true
argument-hint-zh: 基于 {time_window} 的查询模式，给 {target_db} 输出索引优化建议（仅提案）
description: 索引优化建议技能。基于 index_info 的现有索引与基数、slow_log 的查询模式聚类、explain 的计划判读，生成组合索引候选、识别重复与未使用索引、评估写入放大与体积代价，并输出 ADD INDEX / DROP INDEX 提案（含在线 DDL 方案与回滚）。触发词包括"索引""加索引""建索引""索引优化""索引建议""组合索引""覆盖索引""冗余索引""重复索引""未使用索引""索引失效""该不该加索引""index advisor""ADD INDEX"。只出提案，绝不自动执行 DDL。
---

# 索引优化建议技能 (Index Advisor)

## 必需关联知识

所有索引变更提案均遵循[受控变更评审](../safe-ddl-review/SKILL.md)。

本技能是 `db-ops`（智能运维）套件的索引专项能力。它回答三个问题：**该加什么索引、该删什么索引、代价与风险有多大**。输出永远是**提案**（`fix_plan` + 需要时 `execution_plan`），执行由人经审批完成。

## 技能目标

1. 从**真实查询模式**出发（而不是从表结构猜测）生成索引候选，按收益排序。
2. 识别**重复索引、未使用索引、低选择性索引**，给出清理候选与观察期。
3. 量化**代价**：写入放大、空间占用、Online DDL 耗时、复制延迟风险。
4. 每条建议附**验证方式**（EXPLAIN 前后对比）与**回滚步骤**。

## 前置条件

- `target_db` 已绑定；`time_window` 已绑定（用于取真实查询模式，推荐 ≥24h 以覆盖批量任务与业务峰谷）。
- 明确目标表范围：默认只处理慢查询/巡检命中的表；用户要求全库时，先说明代价并分批（每批 ≤10 表）。
- `env` 可读；生产环境的索引变更命中 `deny`，本技能只出提案。

## 核心工作流程

### 1. 取现有索引事实
调用 `index_info`，传参：`target_db`、`tables`（目标表列表）、`include: [columns, cardinality, size_bytes, unused, duplicate, row_count]`。
拿结果并整理成索引台账：`(表, 索引名, 列顺序, 基数, 基数/行数比, 索引体积, 近 30 天使用次数, 是否唯一)`。
判读要点：
- **基数/行数比 < 0.01** → 低选择性列单独建索引收益差（如 `status`、`gender`、`is_deleted`）；
- **使用次数 = 0** → 未使用索引候选（仍需观察期，可能是月度/季度任务）；
- **左前缀包含关系**（`idx(a)` 与 `idx(a,b)`）→ 重复索引，短的那个可删；
- 索引总体积 / 数据体积比值过高（如 >0.8）→ 写入放大风险，需先做清理再新增。

### 2. 取真实查询模式
调用 `slow_log`，传参：`target_db`、`time_window`、`group_by: "fingerprint"`、`top_n: 20`、`fields: [count, avg_ms, rows_examined, rows_sent]`。
对 Top 指纹做**谓词聚类**，抽取每张表的：
- 等值条件列（`=`、`IN`）；
- 范围条件列（`BETWEEN`、`>`、`<`、`LIKE 'abc%'`）；
- 排序列（`ORDER BY` 方向）与分组列（`GROUP BY`）；
- JOIN 连接列；
- SELECT 列表（判断能否做覆盖索引）。
若慢日志不足以覆盖高频查询（例如查询很快但次数极多），补充调用 `db_metrics` 看语句摘要维度，或请用户提供典型 SQL。

### 3. 生成索引候选（遵循最左前缀与列序规则）
对每个查询模式簇生成候选，列序遵循：
1. **等值列在前**（选择性高的更靠前）；
2. **范围列在后**（范围列之后的列无法用于索引定位）；
3. **排序/分组列紧随**，方向尽量一致（混用 ASC/DESC 会导致 filesort）；
4. **JOIN 列**单独考虑，两侧类型与字符集必须一致（否则索引失效）；
5. 若 SELECT 列少且固定，评估**覆盖索引**（把 select 列追加到索引尾部，消除回表）。

对每个候选调用 `explain` 做验证（传 `target_db`、`sql`、`format: "traditional"`、`with_analyze: false`），拿"加索引前"的计划作为对照基线；如目标库支持 `EXPLAIN` 的索引提示（如 `FORCE INDEX`）或有 staging 环境，可在**非生产**环境实测加索引后的计划。
> 生产环境不实测 DDL；用"扫描行量级估算 + 计划推演"给出预估收益，并明确标注为**预估**。

### 4. 收益与代价量化
每个候选给出：

| 维度 | 计算/判据 |
|---|---|
| 预估收益 | 扫描行从 `rows_examined` 降到估算值（等值命中 ≈ 行数/基数；范围命中按选择性估），耗时按扫描量级线性折算，标注"预估，需 EXPLAIN 复核" |
| 覆盖查询数 | 该候选能命中的指纹数量与总耗时占比（多簇共用一个索引优先） |
| 写入放大 | 表每秒写入次数 × 新增索引数；高写入表（>1k TPS）新增索引需重点评估 |
| 空间代价 | 估算 = 行数 × (索引列宽度 + 主键宽度 + ~20B 开销)，与现有磁盘余量对照 |
| 变更代价 | 表行数/体积 → Online DDL 预估耗时（经验：千万行级 5-20 分钟，IO 敏感） |
| 复制影响 | 大表 DDL 在从库串行回放可能推高复制延迟；延迟已告警时优先 gh-ost/pt-osc |

### 5. 清理候选（重复/未使用/低效索引）
- 重复索引（左前缀被更长索引覆盖）→ `DROP INDEX` 候选，风险 L1-L2；
- 未使用索引（30 天 0 次）→ 先**延长观察期到 90 天**或跨一个完整业务周期（月末结算、季度任务），确认后再提；
- 低选择性索引且未被任何查询使用 → 同上；
- **唯一索引、外键支撑索引、主键** 一律不进清理候选；被约束依赖的索引删除会失败或破坏完整性，需先核对约束。
- 清理与新增**不在同一变更窗口**（避免一次变更叠加多份风险，也无法归因效果）。

### 6. 影响面与产出
- 调用 `semantic_search` / `schema_link`（传表名或业务关键词）确认表的下游引用与业务重要性，写入影响面；语义层不可用则标注"血缘不可用，影响面待人工确认"。
- 输出 `fix_plan`：每条含 `动作(完整 DDL 语句) / 类型 index / 破坏性分级 / 预估收益 / 写入放大与空间代价 / 在线方案 / 验证方式(EXPLAIN 前后对比要点) / 回滚预案 / 审批要求`。
- 涉及大表或多条动作时输出 `execution_plan`：变更顺序、每步预估耗时、观察指标（复制延迟、IO、锁等待）、中止条件。
- 需要正式落地评审（分级、锁影响、审批 dock 触发）时转 `safe-ddl-review`。
- 调用 `terminate` 返回 1-2 句摘要（推荐的首条索引 + 预估收益 + "未执行，需审批"）。

## 完整流程示例

```
问题：orders_prod 的 orders 表该加什么索引（env=production，时间窗最近 7 天）

Step 1: index_info(target_db="orders_prod", tables=["orders"],
                   include=[columns,cardinality,size_bytes,unused,duplicate,row_count])
  → 19.2M 行 / 数据 24GB / 索引 6GB
    PRIMARY(id)、uk_order_no(order_no)、idx_status(status: 基数 6, 比值 3e-7, 近 30 天使用 0 次)、
    idx_created_at(created_at: 基数 1.1M)
    无 user_id 相关索引

Step 2: slow_log(target_db="orders_prod", time_window="<最近 7 天>", group_by="fingerprint",
                 top_n=20, fields=[count,avg_ms,rows_examined,rows_sent])
  → 簇 A（占总慢耗时 61%）：WHERE user_id=? AND created_at BETWEEN ? AND ? ORDER BY created_at DESC LIMIT 20
       count=86,000 avg=1,860ms rows_examined=1.9M rows_sent=20
    簇 B（占 12%）：WHERE user_id=? AND status=? ORDER BY id DESC
    簇 C（占 7%）：WHERE order_no=?（已命中 uk_order_no，无需新索引）

Step 3: explain(target_db="orders_prod", sql="<簇 A 样例>", format="traditional", with_analyze=false)
  → type=ALL key=NULL rows=1,920,000 filtered=0.10 Extra="Using where; Using filesort"
    候选生成：等值列 user_id 在前 + 范围/排序列 created_at 在后
    ⇒ idx_user_created (user_id, created_at)  同时消除 filesort（排序方向一致，LIMIT 可提前终止）
    簇 B 亦可用该索引前缀 user_id（status 选择性差，不入索引）

Step 4:（量化）
    预估收益：type ALL→ref，扫描行 1.9M → ~40（19.2M / user_id 基数估算），单次 1.86s → 预估 <20ms
    覆盖：簇 A + 簇 B，合计占总慢耗时 73%
    写入放大：orders 写入 ~300 TPS，新增 1 个二级索引 ⇒ 写路径 +1 次索引维护，评估可接受
    空间：19.2M × (8B bigint + 5B datetime + 8B PK + ~20B) ≈ 0.8-1.0GB（磁盘余量需 >5GB）
    变更代价：19.2M 行，INPLACE/LOCK=NONE 预估 8-15 分钟，IO 敏感；当前复制延迟峰值 42s ⇒ 建议 gh-ost

Step 5:（清理）idx_status：30 天 0 使用 + 基数 6 ⇒ 观察 90 天后再评估 DROP，不与新增同窗口

Step 6: semantic_search(query="orders 表 下游 引用", layer="mysql_prod", top_k=5)
  → 3 个报表数据集 + 1 条实时同步链路引用；加索引不改读语义，但 DDL 期间 IO 上升可能推高同步延迟

  fix_plan：
   [F1] ALTER TABLE orders ADD INDEX idx_user_created (user_id, created_at), ALGORITHM=INPLACE, LOCK=NONE;
        L2 ｜ 预估扫描行 1.9M→~40 ｜ 验证：EXPLAIN 应为 type=ref, key=idx_user_created, 无 filesort
        回滚：ALTER TABLE orders DROP INDEX idx_user_created;
        审批：env=production ⇒ **deny（仅提案）**，走变更流程 + gh-ost + 低峰窗口（避开 23:00-01:00）
   [F2] idx_status 观察 90 天后评估清理 ｜ L1-L2 ｜ confirm（生产 deny）｜ 不与 F1 同窗口
  terminate(result="orders 表建议新增 idx_user_created(user_id, created_at)，预估覆盖 73% 慢耗时、扫描行 1.9M→~40；生产环境 DDL 默认拒绝，提案未执行。")
```

## 注意事项（含安全红线）

- **只提案不执行**：本技能输出的每一条 `ADD INDEX` / `DROP INDEX` 都是提案。`ddl` 是受控工具，每次调用触发审批 dock；**生产环境 `ddl` 命中套件 `deny` 规则**，此时不得发起调用，只输出提案与变更流程指引。`env` 读不到时按 production 处理。
- **不得把 `ddl` 写入 once/session/always 记忆白名单**；用户拒绝后不得改参数重试、不得拆成多条小 DDL 规避阈值。
- **列序即成败**：范围列之后的列无法用于索引定位；混用排序方向会残留 filesort。生成候选后必须用 `explain` 复核，不能只看"列都在索引里"。
- **类型/字符集不一致会让索引失效**（JOIN 两侧 varchar vs int、utf8 vs utf8mb4），必须先核对再建议。
- **收益要标"预估"**：生产不实测 DDL，任何耗时/扫描行下降都是估算，需附验证方式（EXPLAIN 前后对比）。
- **先看代价再提建议**：高写入表（>1k TPS）、磁盘余量不足、复制延迟已告警的情况下，新增索引可能是负收益 —— 要在提案里写明并给替代方案（SQL 改写、覆盖索引、读写分离、归档）。
- **清理要有观察期**：未使用索引先观察 90 天或跨一个完整业务周期；唯一索引/主键/外键支撑索引不进清理候选。
- **变更不叠加**：新增与清理分开窗口；一次提案只推一条破坏性动作。
- **大表优先在线方案**：千万行以上优先 `ALGORITHM=INPLACE, LOCK=NONE`，复制延迟敏感时用 gh-ost / pt-online-schema-change；在 `execution_plan` 中写明中止条件（复制延迟 > 阈值、锁等待飙升即暂停）。
- 工具白名单以套件 `tools.allow` 为准：`index_info, slow_log, explain, db_metrics, semantic_search, schema_link, analyze, ddl`；**无 `shell`**，不得用脚本绕过工具执行 DDL。
