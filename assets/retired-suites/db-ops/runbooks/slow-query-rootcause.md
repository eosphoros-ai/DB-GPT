# Runbook · 慢查询根因定位手册

> 套件：`db-ops@1.0.0` ｜ 配套技能：`slow-query-diagnosis`、`index-advisor`、`safe-ddl-review`
> 用途：把"数据库慢了"这类模糊报障，收敛成一条可复核的定位链路：**症状 → 采集 → EXPLAIN 判读 → 根因分类 → 修复动作与风险等级**。
> 读者：DBA / 值班工程师 / Agent（作为 SOP 的展开细则）。
> 安全前提：全链路**只读**；所有修复动作只出提案，DDL/ANALYZE 必审批，**生产 DDL 默认 deny**。

---

## 0. 使用前必读

| 约束 | 说明 |
|---|---|
| 必须先绑定 | `target_db`（目标库）+ `time_window`（绝对时间区间，≤7 天，超限分段） |
| 环境识别 | 读不到 `env` 时**按 `production` 处理**（就高不就低） |
| 采集节点 | 优先只读从库/备库；采集自主库需在报告标注"采集自主库，已限流" |
| 采集节制 | `top_n` 默认 10；预估扫描 >50GB 的日志采集会命中 confirm 规则 |
| 手册中的 SQL | 仅供**人类 DBA 参考**与工具实现对照；Agent 只能通过套件白名单工具（`slow_log`/`explain`/`db_metrics`/`index_info`/`schema_link`/`semantic_search`）获取数据，**无 `shell`、无 `sql_execute`**，不得自行拼 SQL 执行 |

---

## 1. 症状分诊（先分类，再采集）

不同症状的第一采集动作不同，避免"上来就拉全量慢日志"。

| 症状 | 典型报障话术 | 第一动作 | 重点看 |
|---|---|---|---|
| 突发变慢（分钟级） | "刚才还好好的，现在接口全超时" | `db_metrics` 5m 粒度看拐点 | QPS 突增、连接数打满、锁等待、复制延迟、IO 饱和 |
| 渐进变慢（天/周级） | "这周越来越慢" | `db_metrics` 6h 粒度 + `slow_log` 7 天聚合 | 数据量增长、碎片、统计信息过期、索引失效 |
| 周期性变慢 | "每天凌晨就慢" | `db_metrics` 定位固定时段 + `slow_log` 同窗口 | 批量任务、备份窗口、统计任务、报表跑批 |
| 单条 SQL 慢 | "这个接口 5 秒" | `explain` 直接判读 + `index_info` | type/key/rows/Extra、索引缺失 |
| 偶发超时（P99 抖动） | "平均很快，偶尔超时" | `slow_log` 看 `max_ms` vs `avg_ms` + 锁等待 | Lock_time、长事务、MDL 等待、checkpoint 抖动 |
| 写入慢 / 更新卡顿 | "UPDATE 很慢" | `slow_log` 取 `lock_time` + `db_metrics` 长事务 | 锁等待、大事务、索引过多导致写放大 |
| 全库卡顿 | "整个库都不行了" | `db_metrics` 全维度 + 连接/IO/内存 | 连接数打满、磁盘满、缓冲池命中率骤降、主库宕机前兆 |

> **分诊口诀**：先看指标定"面"，再看慢日志定"点"，最后 EXPLAIN 定"因"。跳过第一步直接看点，容易把**放大因素**当成**主根因**。

---

## 2. 采集动作清单（工具 + 参数 + 拿什么）

### 2.1 负载基线（`db_metrics`）
```
db_metrics(
  target_db="<库>",
  time_window="<绝对区间，如 2026-10-21T22:00:00+08:00/2026-10-22T02:00:00+08:00>",
  granularity="5m",                 # 24h 窗→5m；7d 窗→1h；30d 窗→6h
  metrics=[connections_usage, qps, tps, slow_query_rate, slowest_statement_ms,
           buffer_pool_hit_ratio, tmp_table_on_disk_ratio, disk_io_util, disk_usage,
           replication_lag, lock_waits, deadlocks, long_transactions],
  aggregate=[avg, p95, max],        # 只看均值会漏毛刺，必须有 p95/max
  compare={baseline: "previous_period"}
)
```
**拿什么**：每指标的 `avg/p95/max`、拐点时刻、相对基线偏离百分比。
**判读**：慢查询率上升是否与 QPS 突增 / 缓冲池命中率下降 / 复制延迟 / IO 饱和**时间重合**（重合 = 相关性线索，非因果结论）。

参考对照（人类 DBA 手工核对时可用，只读）：
```sql
-- 全局状态快照（只读）
SHOW GLOBAL STATUS WHERE Variable_name IN
 ('Threads_connected','Threads_running','Slow_queries','Questions','Com_update',
  'Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads',
  'Innodb_row_lock_waits','Innodb_row_lock_time_avg','Created_tmp_disk_tables');
SHOW GLOBAL VARIABLES LIKE 'long_query_time';
```

### 2.2 慢日志聚合（`slow_log`）
```
slow_log(
  target_db="<库>", time_window="<同上>",
  min_duration_ms=500,              # 长尾排查降到 200；只看严重慢用 1000
  group_by="fingerprint",           # 必须去参数化聚合，否则被同一模板的海量条目淹没
  top_n=10,
  fields=[count, avg_ms, max_ms, rows_examined, rows_sent, lock_time, user, host, db]
)
```
**拿什么**：Top N 指纹 + 每条的次数/耗时/扫描行/返回行/锁时间。
**必算两个派生指标**：
- `总耗时 = count × avg_ms` → **按总耗时重排序**，通常前 3 条占 70%+，这才是治理重点；
- `扫描放大比 = rows_examined / max(rows_sent, 1)` → `>1000` 强烈指向缺索引或大扫描。

参考对照（只读）：
```sql
-- 语句摘要（若 performance_schema 可用）
SELECT DIGEST_TEXT, COUNT_STAR, AVG_TIMER_WAIT/1e9 AS avg_ms,
       SUM_ROWS_EXAMINED, SUM_ROWS_SENT, SUM_LOCK_TIME
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;
```

### 2.3 执行计划（`explain`）
```
explain(target_db="<库>", sql="<Top 慢查询的参数化样例，必要时补样例值>",
        format="traditional", with_analyze=false)
```
> ⚠️ **红线**：`with_analyze=true`（`EXPLAIN ANALYZE`）会**真实执行**语句。写语句一律禁用；只读 SELECT 也需先说明代价并获确认。生产库禁用 `EXPLAIN FOR CONNECTION` 之外的任何执行型诊断，除非已批准。

### 2.4 索引与体量（`index_info`）
```
index_info(target_db="<库>", tables=["<涉及表，按需列举>"],
           include=[row_count, columns, cardinality, size_bytes, unused, duplicate])
```
**拿什么**：行数、数据/索引体积、索引清单与列序、基数、未使用索引、重复索引。
**必算**：`基数/行数比`（选择性）；`<0.01` 的低选择性列单独建索引收益差。

参考对照（只读）：
```sql
SHOW INDEX FROM orders;                       -- 索引与基数
SELECT table_rows, data_length, index_length, data_free
FROM information_schema.tables
WHERE table_schema='<库>' AND table_name='<表>';   -- 体量与碎片
```

### 2.5 影响面（`schema_link` / `semantic_search`，可选）
```
schema_link(target_db="<库>", tables=["<表>"])
semantic_search(query="<表名> 下游 引用 owner 血缘", layer="mysql_prod", top_k=5)
```
**拿什么**：表的业务含义、owner、下游数据集/同步链路 —— 用于评估变更影响面与通知范围。语义层不可用时标注"血缘不可用，影响面待人工确认"（binder 会降级为 DBSummary）。

---

## 3. EXPLAIN 判读表

### 3.1 `type` 访问类型（从好到坏）
| type | 含义 | 判读 |
|---|---|---|
| `system`/`const` | 主键或唯一索引等值命中，最多 1 行 | 健康 |
| `eq_ref` | JOIN 中被驱动表用主键/唯一索引 | 健康 |
| `ref` | 非唯一索引等值命中 | 健康（最常见目标态） |
| `fulltext` | 全文索引 | 视场景 |
| `ref_or_null` | ref + IS NULL | 可接受 |
| `index_merge` | 多索引合并 | ⚠️ 常意味着缺一个合适的组合索引 |
| `unique_subquery`/`index_subquery` | 子查询索引命中 | 可接受 |
| `range` | 索引范围扫 | 可接受，关注 `rows` 量级 |
| `index` | **全索引扫**（扫完整棵索引树） | ⚠️ 坏信号，多为覆盖索引扫描但范围过大 |
| `ALL` | **全表扫** | 🔴 坏信号，首要治理对象 |

### 3.2 关键字段
| 字段 | 健康 | 告警 | 说明与动作 |
|---|---|---|---|
| `possible_keys` | 非空 | `NULL` | 无候选索引 ⇒ **缺索引**，转 `index-advisor` |
| `key` | 命中预期索引 | `NULL` 或选了低选择性索引 | 有候选却没选 ⇒ **坏计划**（统计失真/低选择性/隐式转换） |
| `key_len` | 覆盖主要条件列 | 明显偏短 | 组合索引只用到前缀列 ⇒ 索引列序不当或条件写法破坏 |
| `rows` | 接近返回量级 | 百万级 | 预估扫描行；配合 `filtered` 看有效比例 |
| `filtered` | >10% | <1% | 过滤后剩余比例极低 = 扫了大量无用行 |
| `ref` | 常量/合理列 | — | JOIN 连接键是否正确 |
| `Extra` | `Using index` | `Using filesort`、`Using temporary`、`Using where` + `ALL`、`Using join buffer` | filesort=排序无索引支撑；temporary=分组/去重落临时表；join buffer=JOIN 无索引 |
| `partitions` | 命中预期分区 | 全分区扫 | 分区裁剪失效（条件不含分区键） |

### 3.3 常见 `Extra` 组合速查
| Extra | 典型成因 | 处理方向 |
|---|---|---|
| `Using where; Using filesort` + `type=ALL` | ORDER BY 列无索引且需全表扫 | 建组合索引（等值列 + 排序列，方向一致） |
| `Using index; Using filesort` | 覆盖索引但排序不匹配 | 调整索引列序使排序可走索引 |
| `Using temporary; Using filesort` | GROUP BY + ORDER BY 列不一致 | 统一分组/排序列，或改写 SQL |
| `Using join buffer (Block Nested Loop / hash join)` | JOIN 列无索引 | 给被驱动表 JOIN 列建索引；核对两侧类型与字符集一致 |
| `Using where` + `type=index` | 全索引扫过滤 | 建更精准的索引或改写条件 |
| `Impossible WHERE` | 条件恒假 | 应用侧逻辑问题，非 DB 问题 |
| `Select tables optimized away` | 聚合可被索引直接满足 | 健康 |

---

## 4. 根因分类表（现象 → 根因 → 修复动作 → 风险等级）

风险等级定义（与 `safe-ddl-review` 一致）：**L0** 只读 ｜ **L1** 低风险变更（秒级、不重建） ｜ **L2** 中风险（重建/长 IO/短暂锁） ｜ **L3** 高风险或不可逆。
审批：**生产环境所有 DDL = deny**（走线下变更流程）；`analyze` 任意环境 = confirm。

### 4.1 缺索引 / 索引未命中
- **判定信号**：`type=ALL`、`possible_keys=NULL`、扫描放大比 >1000、`index_info` 显示 WHERE/JOIN/ORDER BY 列无可用索引。
- **修复动作**：
  | 动作 | 等级 | 审批 |
  |---|---|---|
  | `ADD INDEX` 组合索引（小表 <100 万行） | L1 | confirm（生产 deny） |
  | `ADD INDEX`（大表，INPLACE/LOCK=NONE 或 gh-ost） | L2 | confirm（生产 deny） |
  | SQL 改写让条件可用现有索引（应用侧） | L0 | 无需 DB 变更 |
- **注意**：列序遵循"等值在前、范围在后、排序紧随"；JOIN 两侧类型/字符集必须一致。

### 4.2 坏执行计划（有索引但没用好）
- **判定信号**：`possible_keys` 有值而 `key=NULL` 或选了低选择性索引；`index_info` 基数与实际行数偏差巨大；`index_merge` 频繁出现。
- **修复动作**：
  | 动作 | 等级 | 审批 |
  |---|---|---|
  | SQL 改写（去掉索引列上的函数/隐式转换、`OR` 改 `UNION ALL`、避免前导通配 `LIKE '%x'`） | L0 | 无需 DB 变更 |
  | `ANALYZE TABLE` 刷新统计信息 | L1（大表 L2） | **confirm**（锁表/资源影响；生产大表需避峰 + DBA 在场） |
  | 删除误导优化器的低选择性/冗余索引 | L2 | confirm（生产 deny） |
  | 优化器 hint / `optimizer_switch` 调整 | L1-L2 | confirm（配置变更，需变更单） |
- **注意**：`ANALYZE` 后计划可能突变，必须复核关键查询计划；不要在同一窗口叠加多项变更。

### 4.3 锁等待 / 并发争用
- **判定信号**：`lock_time` 占耗时比例高而 `rows_examined` 小；`db_metrics` 锁等待/死锁上升；慢查询与大批量写窗口重合；长事务存在。
- **修复动作**：
  | 动作 | 等级 | 审批 |
  |---|---|---|
  | 定位并拆分大事务（应用侧） | L0 | 无需 DB 变更 |
  | 给锁范围过大的查询补索引（缩小锁范围） | L1-L2 | confirm（生产 deny） |
  | 终止长事务 / 杀会话 | L2（影响在途业务） | confirm（破坏性，需明确授权） |
  | 调整隔离级别（如 RC）或 `innodb_lock_wait_timeout` | L2 | confirm（配置变更，需变更单 + 全链路评估） |
- **注意**：MDL 等待（长事务挡住 `ALTER`）会阻塞整表查询，是生产事故高发点；任何"杀会话"动作都是破坏性的，必须单独审批，不得作为常规手段。

### 4.4 大扫描 / 返回集过大
- **判定信号**：`rows` 百万级、`Using filesort/temporary`、深分页 `LIMIT 1000000,20`、无界查询（无 WHERE 或无 LIMIT）、`SELECT *` 拉大字段。
- **修复动作**：
  | 动作 | 等级 | 审批 |
  |---|---|---|
  | 深分页改游标分页（`WHERE id > ? ORDER BY id LIMIT n`） | L0 | 应用侧 |
  | 加 LIMIT / 收窄时间范围 / 只取必要列 | L0 | 应用侧 |
  | 建覆盖索引消除回表 | L1-L2 | confirm（生产 deny） |
  | 大字段外置对象存储、垂直拆表 | L3 | confirm（生产 deny，需架构评审） |
  | 报表类查询迁只读从库/数仓 | L2 | confirm（架构演进） |
- **注意**：业务库不是数仓，聚合大范围扫描应迁到分析链路（提示用户切 `db-analysis` 套件 + 只读从库）。

### 4.5 SQL 写法问题（索引失效）
- **判定信号**：索引列被函数/表达式包裹、隐式类型转换（varchar 列传数字）、`LIKE '%x'` 前导通配、`OR` 连接非索引列、`!=`/`NOT IN` 大范围、字符集不一致。
- **修复动作**：改写 SQL（L0，应用侧）；必要时补函数索引/生成列索引（L1-L2，confirm，生产 deny）。

### 4.6 资源 / 配置瓶颈
- **判定信号**：缓冲池命中率 <97%、IO util >85%、连接数使用率 >75%、复制延迟升高、临时表落盘比例高。
- **修复动作**：
  | 动作 | 等级 | 审批 |
  |---|---|---|
  | 定位并消除大扫描（缓冲池被冲刷的首因） | L0-L2 | 视动作而定 |
  | 连接池配置调整（应用侧） | L0 | 无需 DB 变更 |
  | `innodb_buffer_pool_size` / `tmp_table_size` 等参数调整 | L2 | confirm（配置变更 + 重启风险，需变更单） |
  | 扩容 / 增加只读节点 | L3 | confirm（架构演进） |
- **注意**：配置类变更不在本套件工具能力内（无 `shell`、无配置写入工具），只能出建议并指向变更流程。

### 4.7 数据分布 / 膨胀 / 碎片
- **判定信号**：`data_free` 比例高、单表行数/体积超阈值、冷数据占比高、无主键表。
- **修复动作**：转 `profile-governance`（归档 L2→L3、碎片重建 L2、补主键 L3、冷热分层 L2-L3），全部 confirm 且生产 deny。
- **注意**：碎片重建需约等量空闲空间；磁盘余量不足时禁止建议。

---

## 5. 定位决策树

```
报障：库慢了
 ├─ Step1 db_metrics 看"面"
 │   ├─ QPS/连接数突增 ────────────► 放大因素：先限流/错峰，再回到 SQL 级定位
 │   ├─ IO 饱和 / 缓冲池命中率骤降 ─► 找大扫描 SQL（Step2）+ 评估资源瓶颈（4.6）
 │   ├─ 复制延迟升高 ──────────────► 查大事务 / 大 DDL / 回放并行度；影响读一致性需上报
 │   ├─ 锁等待 / 死锁上升 ─────────► 走 4.3 锁路径
 │   └─ 指标全部正常但用户说慢 ────► 疑非 DB 侧（应用/网络/中间件），说明并移交
 └─ Step2 slow_log 看"点"（按总耗时排序 Top3）
     ├─ 扫描放大比 >1000 ──► Step3 explain
     │    ├─ type=ALL & possible_keys=NULL ─► 4.1 缺索引 → index-advisor
     │    ├─ type=ALL & possible_keys 有值 ─► 4.2 坏计划 → 改写 / ANALYZE(confirm)
     │    ├─ type=index / range 但 rows 巨大 ► 4.4 大扫描 → 改写 / 覆盖索引
     │    └─ Extra: join buffer ────────────► JOIN 列缺索引 / 类型不一致
     ├─ lock_time 占比高 & 扫描行小 ────────► 4.3 锁等待（多为次生现象，需回溯被谁阻塞）
     └─ max_ms >> avg_ms（偶发）────────────► 查同时段指标：checkpoint / 备份 / DDL / 长事务
```

**三条判读纪律**：
1. **相关不等于因果** —— 指标拐点只提供线索，主根因必须有 SQL 级证据（EXPLAIN + 索引事实）。
2. **区分主根因 / 放大因素 / 次生现象** —— UPDATE 锁等待常常是被大扫描拖住的次生表现，治主根因即消。
3. **未复现就说未复现** —— 扩窗一次（最多 ×4）仍无慢查询，结论写"该窗口无慢查询事件"，转巡检建议，不编造。

---

## 6. 诊断报告模板（`diag_report`）

```markdown
## 诊断报告 · <target_db> · <time_window>
- 环境：<env>（生产标识）｜ 采集节点：<主库/只读从库> ｜ 套件：db-ops@1.0.0
- 结论摘要：<1-3 句：什么问题、影响多大、根因类别>
- 风险分级：P0 生产受损 / P1 显著劣化 / P2 优化项 → 本次为 <级别>

### 慢查询 Top N（按总耗时排序）
| # | 指纹 | 次数 | 平均/最大耗时 | 扫描行/返回行 | Lock_time | 总耗时占比 | 根因标签 |

### 证据链（citation）
- slow_log：<条目/窗口/聚合口径>
- explain：<table, type, key, rows, filtered, Extra>
- index_info：<行数/体积/索引清单/基数/未使用>
- db_metrics：<指标、拐点时刻、基线偏离>

### 根因判定
- 主根因：<类别 + 依据>
- 放大因素：<...>
- 次生现象：<...>
- 排除项：<已排除的可能与依据>

### 影响面
- 涉及表 / 下游数据集 / 同步链路 / 业务模块 / owner（语义层不可用时标注待人工确认）

### 修复建议概览（详见 fix_plan）
| # | 动作 | 类型 | 等级 | 预估收益 | 审批要求 | 状态 |
（状态一律为「未执行 · 待人工确认」；生产 DDL 标注「deny，走变更流程」）
```

## 7. 修复计划模板（`fix_plan`）

```markdown
| 字段 | 内容 |
|---|---|
| 动作 | 完整可执行语句或应用侧改动描述 |
| 类型 | index / sql_rewrite / config / analyze / archive / partition |
| 破坏性分级 | L0 / L1 / L2 / L3 |
| 预估收益 | 扫描行变化、耗时预估（标「预估」，附验证方式） |
| 锁与资源影响 | 是否 Online、预估耗时、额外空间、复制延迟风险、MDL 风险 |
| 在线方案 | INPLACE+LOCK=NONE / gh-ost / pt-osc / 应用侧灰度 |
| 回滚预案 | 回滚语句 + 分级 + 验证方式；不可逆动作写「回滚成本 = 备份恢复，RTO ≈ X」 |
| 审批要求 | confirm / deny（生产）+ 是否需双人复核与变更单 |
| 状态 | 未执行 · 待人工确认 |
```

---

## 8. 失败与降级速查

| 情形 | 降级动作 | 报告标注 |
|---|---|---|
| 慢日志未开启 / 无权限 | 用 `db_metrics` + 语句摘要（若可用）；请用户开启后复诊 | "慢日志不可用，结论置信度中" |
| 窗口内无慢查询 | 扩窗一次（≤×4），仍无则判定未复现 | "未复现"，不编造 |
| `explain` 失败（SQL 不完整） | 请用户补参数/样例值；仅做静态判读 | "执行计划缺失，静态推断" |
| 指标部分维度缺失 | 用可得维度出局部结论 | 列缺失维度与影响 |
| 语义层未就绪 | 降级 DBSummary；影响面待人工确认 | 水位线标注降级 |
| 根因在应用层（N+1、缓存穿透、批量任务） | 给 DB 侧缓解项 + 明确应用侧待办 | "根因部分在应用层" |
| 工具连续 2 次同类失败 | 停止重试，说明缺口并请求补充信息/授权 | 不进入死循环 |

---

## 9. 安全红线（本手册范围内）

1. 采集阶段**只用只读工具**；`ddl` / `analyze` 每次调用触发审批 dock，**不得**写入 once/session/always 记忆白名单。
2. **生产环境 DDL 默认 deny** —— 不发起调用、不"先试试看"，直接输出提案 + 线下变更流程指引。`env` 未知按 production 处理。
3. **永久禁止**：`shell`、`drop_database`、`truncate`（`tools.deny`）；`DROP/TRUNCATE/RENAME` 形态 DDL（套件层永久 deny）。不提供任何绕过路径。
4. **策略只能加严**：套件无权把核心 deny 放宽；合并顺序恒为 `core deny > suite > core default`。
5. **`EXPLAIN ANALYZE` 视同执行**：写语句一律禁用。
6. **被拒绝后不绕行**：不改参数重试、不换等价工具、不拆批规避阈值。
7. **修复永远是提案**：`fix_plan` 每条必须含"未执行 · 待人工确认"与回滚预案；无回滚不通过评审。
8. **变更不叠加**：一次窗口只推一条破坏性动作。
