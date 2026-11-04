# EXPLAIN 判读要点

## 字段优先级（看计划的顺序）

`type` → `key` / `possible_keys` / `key_len` → `rows` → `filtered` → `Extra`。先看访问类型和实际用到的索引，再看估算行数，最后用 Extra 解释代价来源。

## type 与代价

| type | 含义 | 判读 |
|:---|:---|:---|
| `system`/`const` | 主键/唯一等值 | 最优 |
| `eq_ref` | 连接时每行匹配唯一索引 | 连接场景最优 |
| `ref` | 非唯一等值 | 良好；`rows` 大说明区分度不足 |
| `fulltext`/`range` | 范围扫描 | 可接受，关键看扫多少行 |
| `index` | 全索引扫描 | **别被"走了索引"骗**：`key` 有值但 `type=index` 通常是索引全扫，代价接近全表扫（但顺序可能省掉 filesort） |
| `ALL` | 全表扫描 | 大表即问题；小表（<1k 行）可接受 |

## key_len：最容易被忽略的诊断利器

`key_len` 告诉你**实际用到了联合索引的几列**。计算：`int=4`、`bigint=8`、`datetime=5`、`date=3`、`timestamp=4/5`、`char(n)` = n×字符集字节数（utf8mb4=4）、`varchar` 额外 +2；**可空列 +1**。
- `key_len` 小于索引总长度 → 联合索引在第 X 列后断裂（范围条件右侧失效、缺少前缀列、或该列被函数/类型转换包裹）。
- 这是判断"索引建了但没用全"的最直接证据，比读 SQL 猜可靠。

## filtered 与 rows 的组合解读

- `rows` 大 + `filtered` 低（如 10%）→ 扫了很多行但大部分被 `where` 丢掉 → **索引列顺序不对，把高区分度且等值的列前移**。
- `rows` 与实际行数接近 → 优化器认为只能扫全表（缺可用索引）。
- `rows` 与实际差数量级 → **统计信息失真**，先 `ANALYZE TABLE`（小表 L1，大表 L2 且需说明耗时）再重看计划，不要据此改索引。
- `rows=1` 但耗时很高 → 成本不在本节点，往连接顺序外层或锁等待/回表次数看。

## Extra 判读

| Extra | 含义 | 处置方向 |
|:---|:---|:---|
| `Using index` | 覆盖索引，无回表 | 目标态 |
| `Using where` | 存储引擎返回后 server 层再过滤 | 有回表，看能否覆盖 |
| `Using index condition` | ICP，索引层过滤部分条件 | 已是优化，通常不必再动 |
| `Using filesort` | 额外排序 | 排序列接不到索引后缀，或跨表排序（**多表连接时 filesort 无法靠索引消除**）；给 `sort_buffer_size`/预排序/改驱动顺序方案 |
| `Using temporary` | 临时表（常在 `GROUP BY`/`DISTINCT`/`UNION`） | 分组列能否走索引顺序；`tmp_table_size`/`max_heap_table_size` 是否溢出到磁盘 |
| `Using join buffer (Block Nested Loop)` | 5.7 无索引连接 | **必须**给被驱动表连接列加索引 |
| `Using join buffer (hash join)` | 8.0.18+ | 连接列无索引的兜底；数据量大仍需索引 |
| `Using MRR` / `Using index skip scan` / `removable` / `attached_condition` | 8.0 特性 | 出现即说明优化器在做额外努力，评估是否索引结构本身别扭 |
| `Impossible WHERE` / `Select tables optimized away` | 逻辑短路 | 正常，SQL 条件恒假或聚合走元数据 |

## 8.0 的 FORMAT=TREE / EXPLAIN ANALYZE 读法

```
-> Filter: ... (cost=1.23e+05 rows=1000) (actual time=12.3..45.6 rows=998 loops=1)
    -> Index range scan on t using idx_a (a BETWEEN 1 AND 100), (cost=... rows=...)
```
- **`cost` 是估算，`actual time`/`rows` 是实测**：只看 cost 会误判，必须优先用 `EXPLAIN ANALYZE`（注意它真执行，DML 严禁在主库跑）。
- **`loops` 是被外层驱动的次数**：真实代价 ≈ `actual time × loops`。连接内层节点 loops 上万时，即便单次极快也是瓶颈。
- **`(never executed)`** → 分支未走，说明条件与预期不符（往往是隐式类型转换或条件写错）。
- 找 **第一个 `actual rows` 与 `cost rows` 差数量级** 的节点，那里就是估算失真的源头。
- `materialized`、`(subquery N)`、`sort`、`grouping operation` 是常见的大代价块，看它的输入行数是否被过早放大。

## 常见的"计划看起来对但实际慢"

1. `rows` 少但**回表随机 IO** 多（二级索引 → 主键回表，物理分散）→ 考虑覆盖索引或按主键排序后批量取。
2. 执行计划**间歇性变化**（同一 SQL 有时快有时慢）→ 参数嗅探式的统计信息临界点，或 `optimizer_switch`/数据分布漂移。给出稳定化手段（`FORCE INDEX` 局部化、统计信息刷新、SQL 拆分）。
3. SQL 自身 `LIMIT` 很快，但整体慢 → 时间花在**锁等待或 MDL**，不在执行计划里。查 `innodb_trx` / processlist 的 `State`。
4. 分区表：`EXPLAIN partitions`（8.0）看是否命中分区裁剪，未裁剪时索引再好也白搭。
