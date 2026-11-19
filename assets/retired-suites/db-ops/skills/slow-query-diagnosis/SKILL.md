---
name: slow-query-diagnosis
name_zh: 慢查询诊断
name_en: Slow Query Diagnosis
description_en: Collect slow logs, group SQL fingerprints, interpret execution plans, and identify index, scan, locking, query, or resource issues. Produce evidence-based diagnostics and repair proposals.
argument-hint-en: Collect slow queries from {target_db} over {time_window} and rank the top 10 fingerprints
command: /slowlog
user-invocable: true
argument-hint-zh: 拉取 {target_db} 最近 {time_window} 的慢查询并按指纹聚合 Top10
description: 数据库慢查询诊断技能。用于采集慢日志、按 SQL 指纹聚合、解读 EXPLAIN 执行计划并归类根因（缺索引/坏计划/锁等待/大扫描/SQL 写法/资源瓶颈），产出带证据链的诊断报告与待审批的修复提案。触发词包括"慢查询""慢 SQL""慢日志""查询变慢""根因""执行计划""EXPLAIN""全表扫""filesort""锁等待""接口超时""数据库卡""slow query""为什么这么慢"。只读优先，DDL/ANALYZE 仅出提案不自动执行。
---

# 慢查询诊断技能 (Slow Query Diagnosis)

## 必需参考

读取[根因定位手册](../../runbooks/slow-query-rootcause.md)、
[生产安全清单](../../runbooks/production-safety-checklist.md)和
[运维 SOP](../../prompts/ops-playbook.md)；修复动作按
[受控变更评审](../safe-ddl-review/SKILL.md)输出提案。

本技能是 `db-ops`（智能运维）套件的核心技能，实现"采集 → 聚合 → 根因 → 诊断 → 修复提案"五步链中前四步的完整闭环，并把第五步收敛为**可评审的提案**。适用对象是企业业务库（OLTP），不是数仓大查询调优。

## 技能目标

1. 在**指定目标库 + 指定时间窗**内定位"谁最慢、慢多少、为什么慢"，结论按总耗时占比排序，不逐条罗列。
2. 每条根因都挂**可核对的证据**：慢日志条目、EXPLAIN 字段、指标拐点、索引现状。
3. 明确区分**主根因 / 放大因素 / 次生现象**，避免把锁等待这类次生表现误判为根因。
4. 输出 `diag_report` + `fix_plan` 两类产物；所有破坏性动作标注"未执行 · 待人工确认"。

## 前置条件（缺失即先澄清，不得默认）

- `target_db`：目标库已绑定（未绑定不要"全库扫一遍"）。
- `time_window`：时间窗已绑定，且**转成绝对时间**（"昨晚"→ `2026-10-21T22:00:00+08:00/2026-10-22T02:00:00+08:00`），跨度 ≤7 天。
- `env`：环境标识可读；读不到时**按 production 处理**（就高不就低）。

## 核心工作流程

### 1. 建负载基线（先基线，后慢日志）
- 调用 `db_metrics`，传参：`target_db`、`time_window`（绝对区间）、`granularity: "5m"`、`metrics: [connections, qps, tps, slow_query_rate, buffer_pool_hit_ratio, disk_io, replication_lag, lock_waits]`。
- 拿结果：记录每个指标的**基线值**与**峰值/拐点时刻**。目的是回答"慢是绝对慢，还是被突增流量放大的相对慢"。
- 判定要点：慢查询率上升是否与 QPS 突增、缓冲池命中率下降、复制延迟、批量任务窗口**时间重合**（重合只是相关性，第 5 步才定因果）。

### 2. 采集慢日志并按指纹聚合
- 调用 `slow_log`，传参：`target_db`、`time_window`、`min_duration_ms`（默认 500，长尾排查可降到 200）、`group_by: "fingerprint"`（去参数化）、`top_n: 10`、`fields: [count, avg_ms, max_ms, rows_examined, rows_sent, lock_time, user, host]`。
- 拿结果：得到 Top N 指纹表。**计算 `总耗时 = count × avg_ms` 并重新排序**，同时计算 `扫描行/返回行` 比值。
- 判定要点：
  - `扫描行/返回行 > 1000` → 强烈指向缺索引或大扫描；
  - `lock_time` 占比高而 `rows_examined` 小 → 指向锁等待/并发争用；
  - 单条 `max_ms` 远大于 `avg_ms` → 可能是偶发资源争用或统计信息抖动，需结合第 1 步指标看。

### 3. 解读执行计划（EXPLAIN 判读表）
- 调用 `explain`，传参：`target_db`、`sql`（Top 慢查询的参数化样例，必要时请用户补样例值）、`format: "traditional"`、`with_analyze: false`。
- 拿结果后按下表判读：

| 字段 | 健康值 | 告警信号 | 含义与动作 |
|---|---|---|---|
| `type` | `const`/`eq_ref`/`ref`/`range` | `ALL`、`index` | `ALL`=全表扫；`index`=全索引扫（比全表扫好一点，仍是坏信号） |
| `possible_keys` | 非空 | `NULL` | 无候选索引 → 缺索引，转 index-advisor |
| `key` | 命中预期索引 | `NULL` 或选了低选择性索引 | 有候选却没选 → 坏计划/统计失真，考虑 SQL 改写或统计刷新 |
| `rows` | 接近实际返回量级 | 百万级 | 预估扫描行，配合 `filtered` 看有效比例 |
| `filtered` | >10% | <1% | WHERE 过滤后剩余比例极低 = 扫了大量无用行 |
| `Extra` | `Using index` | `Using filesort`、`Using temporary`、`Using where`+`ALL` | filesort/temporary 常伴随排序分组无索引覆盖 |
| `key_len` | 覆盖主要条件列 | 明显偏短 | 组合索引只用到了前缀列，索引设计不当 |

- **红线**：`with_analyze=true`（`EXPLAIN ANALYZE`）会**真实执行** SQL。写语句一律禁用；只读 SELECT 也需先说明代价并获确认。

### 4. 核对索引现状与表体量
- 调用 `index_info`，传参：`target_db`、`tables`（慢查询涉及的表，**按需列举，不要全库**）、`include: [columns, cardinality, size_bytes, unused, duplicate]`。
- 拿结果：现有索引清单、各索引基数（cardinality）、表行数与数据/索引体积、未使用索引、重复索引。
- 判定要点：
  - WHERE / JOIN / ORDER BY 列**是否被某个索引前缀覆盖**；
  - 基数/行数比值极低（如 `status` 基数 6）→ 低选择性索引，优化器可能不选；
  - 基数与实际行数偏差巨大 → 统计信息过期，属"坏计划"根因，修复提案才是 `analyze`（L1-L2，需审批）。

### 5. 聚合与根因归类
把前四步对齐成一张事实表：`(指纹, 表, count, avg_ms, rows_examined/rows_sent, EXPLAIN 要点, 索引现状, 同时段指标异常)`，然后归类：

| 根因类别 | 判定信号组合 |
|---|---|
| 缺索引 / 索引未命中 | `type=ALL` + `possible_keys=NULL` + 扫描行/返回行比极高 + `index_info` 无对应索引 |
| 坏执行计划 | `possible_keys` 有值但 `key` 选了差的；或基数严重失真；改写 hint 后计划改善 |
| 锁等待 / 并发争用 | `lock_time` 高 + `rows_examined` 小 + 指标锁等待/死锁上升 + 与批量写窗口重合 |
| 大扫描 / 返回集过大 | `rows` 百万级 + `Using filesort/temporary` + 深分页（`LIMIT 1000000,20`）或无界查询 |
| SQL 写法问题 | 索引列被函数包裹、隐式类型转换（varchar 列传数字）、`SELECT *`、`OR` 破坏索引、`LIKE '%x'` 前导通配 |
| 资源 / 配置瓶颈 | 缓冲池命中率下降、磁盘 IO 饱和、连接数打满、复制延迟升高（多为放大因素而非主根因） |
| 数据分布 / 膨胀 | 碎片率高、冷热混存、无归档 → 转 profile-governance |

- 明确标注：**主根因**（贡献最大总耗时且证据充分）、**放大因素**（如批量任务抬升 QPS）、**次生现象**（如被长读拖住的 UPDATE 锁等待）。
- 证据不足时如实写"证据不足"，并列出还需什么（`performance_schema` 语句摘要 / 更宽窗口 / 业务侧确认任务时间）。**不得编造根因。**

### 6. 产出诊断报告与修复提案
- 输出 `diag_report`：结论摘要（1-3 句）+ 慢查询 Top N 表 + 证据链（`citation` 指向慢日志条目/EXPLAIN 片段/指标快照）+ 影响面 + 风险分级（P0/P1/P2）+ 修复建议概览。
- 影响面不清楚时调用 `semantic_search`（传 `query`、`layer`、`top_k`）或 `schema_link` 查表的业务含义与上下游血缘；语义层不可用则标注"血缘不可用，影响面待人工确认"。
- 输出 `fix_plan`：每条动作含 `动作 / 类型 / 破坏性分级(L0-L3) / 预估收益 / 锁与资源影响 / 在线方案 / 回滚预案 / 审批要求`，并统一标注"**未执行 · 待人工确认**"。
- 涉及索引变更时转 `index-advisor` 生成候选；涉及 DDL 落地评审时转 `safe-ddl-review`。
- 调用 `terminate` 返回 1-2 句摘要（根因 + 最重要的一条提案 + 审批状态）。

## 完整流程示例

```
问题：orders_prod 昨晚 22:00-02:00 慢查询根因（env=production）

Step 1: db_metrics(target_db="orders_prod",
                   time_window="2026-10-21T22:00:00+08:00/2026-10-22T02:00:00+08:00",
                   metrics=[connections,qps,slow_query_rate,buffer_pool_hit_ratio,replication_lag,lock_waits],
                   granularity="5m")
  → QPS 1,800→4,600（23:10 起，批量对账窗口）；慢查询率 0.2%→6.8%；
    缓冲池命中率 99.2%→91.4%；复制延迟 0→42s；无死锁

Step 2: slow_log(target_db="orders_prod", time_window=<同上>, min_duration_ms=500,
                 group_by="fingerprint", top_n=10,
                 fields=[count,avg_ms,max_ms,rows_examined,rows_sent,lock_time])
  → #1 SELECT ... FROM orders WHERE user_id=? AND created_at BETWEEN ? AND ?
        ORDER BY created_at DESC LIMIT ?  count=12,480 avg=1,860ms rows_examined=1.9M rows_sent=20 lock_time=0
    #2 order_items WHERE order_id IN (...)  count=31,200 avg=240ms
    #3 UPDATE orders SET status=? WHERE order_no=?  count=2,100 avg=95ms max=3.8s lock_time=1,200ms
    Top3 占总耗时 83%；#1 扫描比 95,000:1 且 lock_time=0 → 扫描问题非锁问题

Step 3: explain(target_db="orders_prod", sql="<#1 样例>", format="traditional", with_analyze=false)
  → table=orders type=ALL possible_keys=NULL key=NULL rows=1,920,000 filtered=0.10
    Extra="Using where; Using filesort"  ⇒ 全表扫 + 文件排序

Step 4: index_info(target_db="orders_prod", tables=["orders","order_items"],
                   include=[columns,cardinality,size_bytes,unused,duplicate])
  → orders 19.2M 行 / 数据 24GB / 索引 6GB；索引仅 PRIMARY(id)、uk_order_no、idx_status(基数 6, 近 30 天 0 使用)
    无 (user_id, created_at) 组合索引

Step 5:（聚合推理，不调工具）
  → 主根因：缺 (user_id, created_at) 组合索引 → 高频用户维度查询全表扫 + filesort
    放大因素：23:10 批量对账任务抬升 QPS 2.5×，大扫描冲刷缓冲池
    次生现象：#3 UPDATE 的锁等待（被长读拖住），非独立根因
    排除项：无死锁、统计信息未严重失真、连接/磁盘未到顶

Step 6: 产出 diag_report（分级 P1）+ fix_plan：
  [F1] ALTER TABLE orders ADD INDEX idx_user_created (user_id, created_at), ALGORITHM=INPLACE, LOCK=NONE;
       L2 ｜ 预估 type ALL→ref、扫描行 1.9M→~40 ｜ 回滚 DROP INDEX ｜ env=production ⇒ **deny，仅提案**
  [F2] order_items 的 IN(5000) 分片为 ≤500/批 ｜ L1 ｜ 应用侧改动，无需 DB 变更
  [F3] idx_status 观察 30 天后评估清理 ｜ L2 ｜ confirm（生产 deny），不与 F1 同窗口
  terminate(result="orders_prod 昨晚慢查询主根因为缺 (user_id, created_at) 组合索引致全表扫；已出 4 条修复提案，全部未执行，生产 DDL 需走变更流程。")
```

## 注意事项（含安全红线）

- **只读优先**：采集阶段只用 `db_metrics` / `slow_log` / `explain`（不带 ANALYZE）/ `index_info` / `semantic_search` / `schema_link`，这些无需审批；`ddl` 与 `analyze` 是破坏性/受控工具，**每次调用都触发审批 dock**，且不得写入 once/session/always 记忆白名单。
- **生产 deny**：`env=production` 时 DDL 命中套件 deny 规则 —— 不发起调用、不"先试试看"，直接给提案 + 线下变更流程指引。`env` 读不到时按 production 处理。
- **不越权**：本技能不执行任何变更，`fix_plan` 中每条动作必须带"未执行 · 待人工确认"与回滚预案。
- **EXPLAIN ANALYZE 视同执行**：会真实运行语句，写语句一律禁用。
- **采集要节制**：单次时间窗 ≤7 天、`top_n` 默认 10、`index_info` 按需列表指定；预估扫描 >50GB 的日志采集会命中 confirm 规则。优先在只读从库采集，采集自主库时在报告标注。
- **被拒绝后不绕行**：审批被拒不得改参数重试、不得换等价工具重试、不得拆成多次小变更规避阈值；改为补强只读诊断。
- **相关 ≠ 因果**：指标拐点与慢查询时间重合只能作为"放大因素"线索，必须有 SQL 级证据（EXPLAIN/扫描比/索引缺失）才能定主根因。
- **未复现就说未复现**：扩窗一次（最多 ×4）仍无慢查询，结论写"该窗口无慢查询事件"，转巡检建议，不编造。
- **工具连续 2 次同类失败**即停止重试，向用户说明缺口并请求补充信息或授权。
- 工具白名单以套件 `tools.allow` 为准：`slow_log, explain, db_metrics, index_info, semantic_search, schema_link, analyze, ddl`；**无 `shell`**，不得用脚本或命令行绕过工具执行 SQL。
