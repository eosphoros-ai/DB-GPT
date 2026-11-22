# SQL 体检报告模板

单条模式用第 1–6 节；批量模式在第 7 节追加汇总清单。文件名：`outputs/sql-doctor-<表名或digest前8位>-<YYYYMMDD>.md`。

---

# SQL 体检报告：<`<db>.<tbl>` / digest 前 8 位>

**基本信息**

| 项 | 值 |
|:---|:---|
| 实例 / 角色 | `<实例>`（主库 / 从库）；MySQL `8.0.x` |
| 数据量 | `<tbl>` ≈ `N` 行 / `X` GB（索引 `Y` GB） |
| 现状耗时 | `t` ms（p95 `t` ms / 日均执行 `n` 次 / 累计耗时占比 `p`%） |
| 目标耗时 | `t'` ms |
| 证据来源 | `EXPLAIN` / `EXPLAIN ANALYZE` / 慢日志 / digest 表（**注明采集时间**） |

## 1. SQL 原文（脱敏）

```sql
-- 参数已脱敏
SELECT ...
```

## 2. 诊断结论

**一句话结论**：`<...>`

| 维度 | 证据 | 判读 |
|:---|:---|:---|
| 访问类型 | `type=ALL` / `key=NULL` | 全表扫描 |
| 实际用到的索引长度 | `key_len=4`（索引总长 13） | 联合索引在 `b` 列断裂 |
| 估算 vs 实际 | `rows=1` vs 实测 12.4 万 | 统计信息失真（命中 I-17） |
| 扫描放大比 | `rows_examined/rows_sent = 3100` | 无效扫描占绝对主导 |
| 排序/分组 | `Using temporary; Using filesort` | 分组列未接索引后缀 |

**命中的失效原因**：`I-06`（范围条件右侧列失效）、`I-12`（回表代价过高）、`I-16`（深分页）
（编号对应 [索引设计手册](index-playbook.md)；判读依据对应 [EXPLAIN 判读要点](explain-reading.md)）

## 3. 优化方案

### 3.1 索引变更
```sql
-- [L2 需审批] 从库先验证；预计耗时 ~X min，额外空间 ~Y GB
ALTER TABLE <db>.<tbl> ADD INDEX idx_status_id_ct (status, id, gmt_create),
  ALGORITHM=INPLACE, LOCK=NONE;
```
列顺序理由：`status` 等值 + 高业务共用性 → `id` 承接 `ORDER BY` 消除 filesort → `gmt_create` 作为覆盖尾巴消除回表。

### 3.2 SQL 改写
```diff
- SELECT * FROM orders WHERE status>0 AND gmt_create>'2026-10-01' ORDER BY id LIMIT 1000000,20;
+ -- 游标分页：用上一页最大 id 定位，避免跳过 100 万行
+ SELECT id, status, gmt_create FROM orders
+  WHERE status>0 AND id > :last_seen_id
+  ORDER BY id LIMIT 20;
```
差异说明：`status>0` 改等值枚举（`IN (1,2)`）以保住联合索引后缀可用；`SELECT *` → 明确列以命中覆盖索引。

## 4. 预期效果

| 指标 | 优化前 | 预期优化后 | 依据 |
|:---|:---|:---|:---|
| 扫描行数 | 1,240,000 | ~400 | `EXPLAIN rows` + 索引选择率推算 |
| 回表次数 | 1,240,000 | 0（覆盖） | 新索引包含全部返回列 |
| 单次耗时 | 8,200 ms | **50–150 ms** | 从库同数据量实测口径 |
| 排序/临时表 | 有 | 无 | `Extra` 消失 |

> 区间而非单点；若从库实测落在区间外，回到 A 组重新归因（不追加"再优化优化"式建议）。

## 5. 副作用与风险

- 索引体积 +`Y` GB；该表日均写入 `n` 万次 → 写放大约 `p`%。
- 新索引可能改变其他 SQL 的执行计划：受影响语句 `digest 前 8 位列表`，需在变更后一并 `EXPLAIN` 复核。
- 统计信息在数据分布剧变后仍可能跳变 → 保留 `FORCE INDEX` 兜底方案：`<SQL>`。
- 未使用的旧索引 `idx_x` 建议观察一个完整业务周期后再评估下线。

## 6. 验证与回滚

```sql
-- [L0] 验证
EXPLAIN FORMAT=TREE <新SQL>;  EXPLAIN ANALYZE <新SQL>;   -- 仅 SELECT，从库执行
FLUSH STATUS; <新SQL>; SHOW SESSION STATUS LIKE 'Handler_read%';

-- [L2] 回滚
ALTER TABLE <db>.<tbl> DROP INDEX idx_status_id_ct, ALGORITHM=INPLACE, LOCK=NONE;
```
验收标准：扫描放大比 ≤ 10，`type ∈ {const,eq_ref,ref,range}`，无 `Using temporary`。
未覆盖的验证项：`<列表>`。

## 7. 批量模式汇总（多条 SQL 时）

| # | 表 | digest 前 8 位 | 日均耗时占比 | 主因（编号） | 方案摘要 | 风险 | 建议责任方 | 优先级 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| 1 | `<tbl>` | `a1b2c3d4` | 32% | I-05 | 加联合索引 | L2 | 订单服务 | P0 |

**共性归因**：`<如"4/6 条集中在 orders 表，缺 (user_id, status, id) 复合索引">`
**结构性建议**：`<如"3 张表无主键，影响复制与恢复能力，建议纳入本季度治理">`
**不需要优化的**：`<列出"当前已可接受"的语句及理由>` —— 这一节同样重要，避免无收益改动。
