---
name: mysql-sql-doctor
version: 1.0.0
description: Diagnose a single SQL or a batch of slow queries — reads EXPLAIN/EXPLAIN ANALYZE output, indexes and table stats, locates the cost driver, and returns a rewritten SQL plus index design with measured expectations.
name_en: SQL Doctor
name_zh: SQL 体检
description_en: Diagnose single or batch slow SQL via execution plans, index analysis and statistics; output rewrite + index recommendation with expected effect.
description_zh: 对单条 SQL 或一批慢查询做体检：解读执行计划、核对索引与统计信息、定位代价来源，输出改写方案与索引建议，并给出可验证的预期。
user-invocable: true
argument-hint: 贴 SQL + EXPLAIN 输出（可选：建表语句、SHOW INDEX、慢日志片段）
argument-hint-en: Paste the SQL + EXPLAIN output (optionally DDL, SHOW INDEX, slow-log snippet)
argument-hint-zh: 贴 SQL + EXPLAIN 输出（可选：建表语句、SHOW INDEX、慢日志片段）
---

# SQL 体检

目标：把"这条 SQL 慢"变成**有数值依据的归因结论 + 可验证的优化方案**。不做泛泛的"建议加索引"。

## 前置

先读知识库基准，判定与红线都以它为准：
- [指标阈值基准](../mysql-ops-knowledge/references/metrics-thresholds.md)
- [只读诊断命令清单](../mysql-ops-knowledge/references/command-cheatsheet.md)
- [安全红线与执行分级](../mysql-ops-knowledge/references/safe-execution-rules.md)

版本/拓扑未知时，先问一句（1 轮内问清，不要连环追问）：MySQL 版本、这条 SQL 跑在主库还是从库、表数据量级、当前耗时与可接受耗时。信息不全也能开工——**明确标注哪些结论是"待验证"**。

## 输入识别（按用户给的东西自适应）

| 用户给什么 | 走什么路径 |
|:---|:---|
| 只有 SQL 文本 | 静态审查：对照 [索引失效清单](references/index-playbook.md) 逐条判定；然后给出**需要采集的 SQL 清单**（建表、`SHOW INDEX`、`EXPLAIN`、行数），不要一次索要全部 |
| SQL + `EXPLAIN` | 走标准 5 步诊断（下方主流程） |
| SQL + `EXPLAIN ANALYZE` 输出 | 直接定位实际耗时最高的节点，优先级最高（这是最有力的证据） |
| 慢日志片段 / `pt-query-digest` 报告 | 批量模式：按总耗时排序，挑 Top 3–5 逐条诊断，其余归入模式类问题 |
| `events_statements_summary_by_digest` 导出 | 同上，用 `SUM_ROWS_EXAMINED/COUNT_STAR` 找扫描放大 |
| 只有"库变慢了"的描述 | 转到 **@实例巡检** 或 **@故障应急**，不要在此技能硬猜单条 SQL |
| 执行计划里的数字与实际严重不符 | 判定为统计信息失真路径，走第 4 步 |

## 主流程（5 步，逐步收敛）

### 第 1 步：建立量化基线
必须拿到（或明确写"待采集"）：驱动表与被访问表的**真实行数**、`EXPLAIN` 的 `rows` 估算、`SHOW INDEX` 的 `Cardinality`、实际耗时、`Handler_read_*`（有则更好）。
核心指标：**扫描放大比 = rows_examined / rows_sent**。> 100 说明大量无效扫描，> 10000 基本确定索引或写法问题。

### 第 2 步：解读执行计划
按 [EXPLAIN 判读要点](references/explain-reading.md) 逐项过，重点判：
- `type` 与 `key` 是否匹配预期；`possible_keys` 有但 `key` 为 NULL → 优化器主动放弃，通常是统计信息/回表成本/隐式转换。
- `rows` 估算与实际数量级偏差 → 统计信息失真。
- `Extra` 组合的严重度排序：`Using filesort` + `Using temporary` > `Using join buffer (Block Nested Loop / hash join)` > `Using where; Using index` (好)。
- 8.0 的 `EXPLAIN ANALYZE`：找 `actual time` 与 `rows` 同时异常大的节点；关注 `(materialized)`、`(retry)`、`BKA`、`Index lookup` 次数。

### 第 3 步：索引层归因
对照 [索引设计手册](references/index-playbook.md) 的失效原因清单**逐条勾选**，输出命中项（不是"可能是"，而是"命中第 X 条，依据是 Y"）。
必须区分四种结论：
- **缺索引** → 给建索引方案（列顺序 + 为什么这个顺序 + 预估索引体积 + 对写放大/空间影响）。
- **有索引但用不上** → 定位到具体失效原因（函数、隐式转换、字符集、最左前缀断裂）。
- **索引不对但可用覆盖索引消除回表** → 给覆盖索引方案，说明牺牲什么（体积、写开销）换什么。
- **索引正确但优化器选错** → 先给验证手段（`FORCE INDEX` 对比、`ANALYZE TABLE` 后重跑），不要直接建议 `optimizer_switch` 全局改动。

### 第 4 步：写法与结构层归因
检查：深分页、`SELECT *`、大 `IN`、`OR` 混合列、子查询可改连接、`ORDER BY` 与索引不匹配、`GROUP BY` 需临时表、函数包裹索引列、排序列与过滤列不同源导致无法同时利用索引、连接顺序（小结果集做驱动表）、`LIMIT` 无 `ORDER BY` 导致的不稳定、事务内等待而非 SQL 本身慢。
区分度不足时明确说"这条 SQL 无法通过索引优化到 X ms，需要走 [改写/归档/预计算/缓存/搜索引擎] 路线"，并给出该路线的代价。

### 第 5 步：输出方案与验证闭环
按 [SQL 体检报告模板](references/sql-doctor-report-template.md) 组织。方案必须包含：
1. **诊断结论**（一句话 + 关键数值 + 命中的失效原因编号）
2. **改法**：SQL 改写前后对照（差异行标注）+ 索引 DDL（含 `ALGORITHM=INPLACE, LOCK=NONE` 判断，或提示转 **@变更评审**）
3. **预期效果**：给出可信区间与依据（如"扫描行数从 1.2M 降到 ~400，预期 8s → 50ms 量级"），不许写"大幅提升"
4. **验证方法**：具体命令（`EXPLAIN ANALYZE` + `SHOW SESSION STATUS LIKE 'Handler_read%'` 前后对比）
5. **副作用**：写放大、空间、执行计划对其他 SQL 的影响、优化器未来跳变风险
6. **风险分级**：按安全红线文件给 L0/L1/L2/L3 打标 + 回滚命令

## 批量模式补充

多条 SQL 时，除逐条结论外必须给出**共性归因**（如"5 条中 4 条是同一张表缺 (status,gmt_create) 复合索引"、"3 条是深分页写法"），并按 **总耗时占比** 排优先级。最后输出一份可交付给业务方的清单：谁改、改哪条、预期收益、风险等级。

## 边界

- 不替用户执行写操作；输出 DDL 时**默认走从库验证 + 变更评审流程**。
- 拿不到真实行数时，禁止用假数据推导结论；改为"待采集 + 假设分支"（"若表 < 10 万行则全表扫描可接受，无需优化"）。
- 存储过程/触发器/外键级联/分区表场景明确提示复杂度和额外验证需求。

## If Connectors Available

If **数据库** 已连接（具备只读账号）：
- 直接采集 `EXPLAIN`、`SHOW CREATE TABLE`、`SHOW INDEX`、表行数与统计信息，无需用户手工粘贴；单次可完成批量诊断。

If **文档平台** 已连接：
- 体检报告自动发布为文档并挂到慢 SQL 治理目录，便于业务方认领。

If **任务工具** 已连接：
- 每条优化建议自动创建待办（含表名、预期收益、风险等级、截止建议）。

If **告警与工单** 已连接：
- 关联同表的历史慢查询工单，避免重复提单；把治理清单回写到对应工单。

If 无连接器（默认）：
- 输出到会话内 + 写入工作目录 `outputs/sql-doctor-<表名或digest>-<日期>.md`；采集命令以可复制代码块给出。
