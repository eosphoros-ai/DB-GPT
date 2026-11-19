# 索引设计手册

编号用于报告引用（"命中 I-07"），保证结论可追溯、不和用户对不上。

## A 组：索引失效原因清单（逐条勾选）

### A1 类型相关
- **I-01 隐式类型转换**：`varchar` 列传数字（`WHERE mobile = 13800138000`）→ 索引失效走全表扫。反向（数字列传字符串）在部分场景仍可用索引但仍有风险。判据：`EXPLAIN` `type=ALL` + 列类型为字符串。
- **I-02 字符集/排序规则不一致**：连接两列 `charset` 或 `collation` 不同（`utf8mb4_general_ci` vs `utf8mb4_0900_ai_ci`）→ 被连接列索引失效。判据：`SHOW FULL COLUMNS` 比对；`EXPLAIN` 里该表 `key=NULL`。
- **I-03 列被函数/表达式包裹**：`DATE(gmt_create)=...`、`SUBSTR(code,1,3)=...`、`id+0=...` → 改范围写法或建 8.0 函数索引。
- **I-04 算术运算/CAST**：`WHERE price*1000 > ?`。

### A2 结构相关
- **I-05 不满足最左前缀**：联合索引 `(a,b,c)` 只过滤 `b`、或跳过 `a`。判据：`key_len` 短于预期。
- **I-06 范围条件右侧列失效**：`(a,b)`，`WHERE a>? AND b=?` → 只用 `a`。改法：把等值列放前，范围列放后。
- **I-07 `OR` 连接不同列**：`(a=1 OR b=2)` → 需 index_merge 或改 `UNION ALL`。
- **I-08 否定与模糊**：`!=`、`<>`、`NOT IN`、`IS NOT NULL`、`LIKE '%xx'`、`LIKE '%xx%'`。`NOT IN` 子查询要改 `NOT EXISTS` / 左连接判空。
- **I-09 `IN` 列表过长**：超过 `range_optimizer_max_mem_size` 时优化器放弃 range → 退化为全表扫。判据：`SELECT @@range_optimizer_max_mem_size`，以及 `IN` 元素上万。改法：分批、临时表连接。
- **I-10 索引区分度不足**：`selectivity = Cardinality/TABLE_ROWS` < 0.01 的单列索引（如 `status`、`is_deleted`）几乎无用；作为联合索引前导列必须结合业务分布判断（**低区分度列做前导有时反而是对的**——如 `status` 只查极少数的异常态，需明确说明这个判断）。
- **I-11 前导列被 `ORDER BY`/`GROUP BY` 依赖但顺序不匹配**：`ORDER BY b` 无 `a` 等值 → 必然 filesort。
- **I-12 二级索引回表代价过高**：优化器主动选全表扫（`possible_keys` 有值但 `key=NULL`）→ 命中率低于约 20–25% 时回表不如扫全表。改法：覆盖索引、缩小返回列、延迟关联。

### A3 写法与优化器相关
- **I-13 驱动表选错**：被驱动表连接列无索引（5.7 `Block Nested Loop` / 8.0 hash join）；应用"小结果集驱动大表"原则。
- **I-14 子查询物化**：`IN (SELECT ...)` 5.6/5.7 可能去相关失败 → 改 `JOIN` 或 `EXISTS`。
- **I-15 `SELECT *`**：阻断覆盖索引，并放大网络/序列化成本。
- **I-16 深分页**：`LIMIT 1000000, 20` → 改游标分页（`WHERE id > ? ORDER BY id LIMIT 20`）或延迟关联（子查询只取主键再连接）。
- **I-17 统计信息失真**：`rows` 估算与实际差数量级；`innodb_stats_persistent_sample_pages` 太小；表刚经历大规模增删或 `ALTER`。
- **I-18 优化器代价临界跳变**：数据量跨过拐点后执行计划突变（同一 SQL 时快时慢）。给出 `FORCE INDEX` 局部兜底 + 长期方案（重建统计、拆分 SQL、加更有区分度的索引）。
- **I-19 排序跨表**：多表连接后 `ORDER BY` 无法用索引消除 filesort，只能靠减少行数或小表先聚合。

### A4 对象本身
- **I-20 表无主键**：影响复制（RBR 回放慢）、在线 DDL、数据订正与恢复能力。**必须列为高优先治理项。**
- **I-21 冗余/未使用索引**：`sys.schema_redundant_indexes`、`schema_unused_indexes`。删除前必须确认统计窗口足够长（覆盖完整业务周期，避免月结/大促 SQL）。
- **I-22 索引数量过多**：单表索引 > 8 个时写放大明显（批量导入场景尤甚），需在方案中量化。
- **I-23 大字段/BLOB/TEXT 上索引**：需前缀索引（`INDEX(col(n))`），并说明 `ORDER BY`/`GROUP BY` 不能用前缀索引。
- **I-24 分区表**：查询不带分区键 → 扫全部分区；主键/唯一键必须包含分区列。

## B 组：设计规则

**联合索引列顺序**（默认策略，需按实际分布调整）：
1. 先放**等值**条件列（多个等值按区分度从高到低，或按业务共用性）
2. 再放 **`ORDER BY` / `GROUP BY`** 列（避免 filesort 的关键）
3. 最后放**范围**条件列
4. 需要消除回表时，把 `SELECT` 用到的列追加为"覆盖尾巴"（权衡体积与写开销）

**判断该不该建索引**：读多写少 + 选择性足够 + 查询模式固定 → 建；否则优先考虑缓存、预计算表、归档、或搜索引擎（ES）承接复杂检索。

**主键选择**：单调递增（`BIGINT AUTO_INCREMENT`）优于随机 UUID（页分裂、缓存效率、二级索引膨胀）。必须用 UUID 时给有序变体（时间前缀 / ULID）或 `uuid_to_bin(uuid(),1,1)`。

**utf8mb4 索引长度**：单列 `varchar(255)` = 1020 字节，超 `innodb_large_prefix`（5.7+ 默认支持 3072 字节，但联合索引总长仍需核算）。长文本用前缀索引，并核对前缀后的区分度：
```sql
SELECT COUNT(DISTINCT LEFT(col,10))/COUNT(*) FROM t;   -- 选前缀长度的依据
```

## C 组：验证与交付

每个索引建议必须给：
```sql
-- 建索引（判断在线 DDL 能力）
ALTER TABLE <tbl> ADD INDEX idx_a_b_c (a,b,c), ALGORITHM=INPLACE, LOCK=NONE;

-- 空间与耗时预估（从库先测）
SELECT ROUND((data_length+index_length)/1024/1024) AS cur_mb FROM information_schema.tables
 WHERE table_schema='<db>' AND table_name='<tbl>';
-- 新索引体积估算 ≈ 列总字节 × 行数 × (1 + 主键指针 8B/列 折算) ，保守按 1.2 倍冗余
```
验证闭环：`EXPLAIN` 前后对照（`key`、`key_len`、`rows`、`Extra`）+ `EXPLAIN ANALYZE` 实测 + `SHOW SESSION STATUS LIKE 'Handler_read%'` 扫描行数对比。
**验收标准（默认）**：扫描放大比 `rows_examined/rows_sent` ≤ 10，且 `type` 至少到 `range`/`ref`，且无 `Using temporary`。达不到就回到 A 组重新归因，不要输出"聊胜于无"的方案。

在线 DDL 不可用（需 COPY、或 5.7 部分场景、或空间不足）时，**转 @变更评审（mysql-change-review）** 出 gh-ost / pt-osc 方案。
