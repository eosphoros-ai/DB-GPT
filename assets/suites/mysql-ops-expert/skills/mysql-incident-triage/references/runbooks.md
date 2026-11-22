# 场景 Runbook 集

每个场景固定四段：**判定特征 → 确认命令 → 止血 → 根治**。命令均标注风险级别（L0 只读 / L1 低风险 / L2 需审批 / L3 高危）。

---

## R1 CPU / load 高（MySQL 引起）

**判定特征**：`us` 为主；`Threads_running` >> 核数；慢查询数与 QPS 同步上升。
**确认**：`SHOW FULL PROCESSLIST` 按 `time` 排序 + `events_statements_summary_by_digest ORDER BY SUM_TIMER_WAIT DESC LIMIT 10`。

**止血**
- [L2] 杀耗时最长的只读 SELECT：`KILL <id>;`（先确认 `command='Query'` 且 SQL 为 SELECT）
- [L2] 应用侧限流 / 降级非核心读；开启缓存兜底
- [L1] 临时提高 `thread_stack` 无关，**不要**用调 `innodb_thread_concurrency` 当万能药（可能进一步降吞吐），若使用需说明观察指标与回退值

**根治**：转 @SQL 体检。若为流量突增：容量评估 + 读写分离 + 缓存；若为定时任务/备份撞峰：错峰。
**排除项**：`sy` 高 → 连接风暴或 `thread_cache_size` 太小（`Threads_created` 增速判断）；`wa` 高 → 走 R6。

---

## R2 连接数打满

**判定特征**：报 `ERROR 1040: Too many connections`；`Threads_connected ≈ max_connections`。
**确认**：按来源聚合
```sql
SELECT SUBSTRING_INDEX(host,':',1) ip, user, COUNT(*) c,
       SUM(command='Sleep') sleeping, MAX(time) max_t
FROM information_schema.processlist GROUP BY 1,2 ORDER BY c DESC;
```

**止血**
- 先进管理通道：8.0 `mysql -u <admin_user> --protocol=admin`（需 `admin_address` 已配）；或 `extra_port`；云 RDS 走控制台"临时提升连接数"。
- [L2] 批量清理长时间 Sleep（先生成清单再执行）：
```sql
SELECT CONCAT('KILL ',id,';') FROM information_schema.processlist
 WHERE command='Sleep' AND time>300 ORDER BY time DESC LIMIT 200;
```
- [L1] 临时上调：`SET GLOBAL max_connections = <new>;` —— 先算内存总账（会话 buffer × 新增连接），回退值必须记录。
- 若 `Threads_running` 同样高：本质是慢 SQL 占连接，回到 R1/R5，**杀连接只是扬汤止沸**。

**根治**：应用连接池上限与 `wait_timeout`/`interactive_timeout` 对齐（池 idle 回收 < 服务端超时）；接入 proxy（ProxySQL/MySQL Router/云代理）；修复池泄漏。

---

## R3 锁等待超时 / 死锁

**判定特征**：`Lock wait timeout exceeded`；`Innodb_row_lock_current_waits > 0`；processlist 大量 `Waiting for table metadata lock`。

**行锁：定位持锁方（8.0）**
```sql
SELECT r.trx_mysql_thread_id wait_thd, LEFT(r.trx_query,80) wait_sql,
       b.trx_mysql_thread_id blk_thd, LEFT(b.trx_query,80) blk_sql,
       b.trx_started, TIMESTAMPDIFF(SECOND,b.trx_started,NOW()) blk_sec,
       b.trx_rows_modified
FROM performance_schema.data_lock_waits w
JOIN information_schema.innodb_trx r ON r.trx_id=w.REQUESTING_ENGINE_TRANSACTION_ID
JOIN information_schema.innodb_trx b ON b.trx_id=w.BLOCKING_ENGINE_TRANSACTION_ID;
```
5.7 用 `information_schema.innodb_lock_waits` + `innodb_trx`。

**止血**
- **优先联系持锁事务的业务方提交/回滚**，而不是 `KILL` 等待方（杀等待方只会换个位置等）。
- [L2] 持锁方不可达时 `KILL <blk_thd>;` —— ⚠️ 大事务回滚耗时可能远大于等待，先看 `trx_rows_modified`：修改行数达百万级时，回滚期间锁仍不释放，需评估"等它跑完"是否更优。
- [L1] 缓解：`SET GLOBAL innodb_lock_wait_timeout = <n>;`（延长等待以让持锁方自然结束，注意这会拉长应用侧超时感受）

**MDL 场景（DDL 卡住 → 后续全部堵）**
```sql
SELECT * FROM performance_schema.metadata_locks WHERE LOCK_STATUS='PENDING';
```
止血：**先杀掉引起阻塞的未完成事务或那个 DDL 会话本身**（杀 DDL 是安全且推荐的，MDL 立即释放），不要杀下游查询。

**死锁**：`SHOW ENGINE INNODB STATUS\G` 读 `LATEST DETECTED DEADLOCK`。判断是"设计固有"还是"新逻辑引入"。
**根治**：缩小事务粒度（**严禁事务内含 RPC/外呼**）、统一加锁顺序、给更新语句走精确索引以缩小锁范围、必要时业务层重试 + 幂等。

---

## R4 整体变慢（无单一 SQL 显眼）

**判定顺序（按概率）**
1. **变更对齐**：故障点前 2h 内的发布/DDL/参数/扩缩容/HA 切换 → 有则优先回退。
2. **执行计划跳变**：Top digest 的 `avg_timer` 环比暴涨但 `COUNT_STAR` 未涨 → 统计信息或数据量临界。[L2] `ANALYZE TABLE <tbl>;`（大表耗时需评估）后复测。
3. **资源被抢**：同机其他进程、云 IO 突发额度耗尽、备份/导出任务、监控 agent。
4. **锁/事务**：R3 的三条查询跑一遍，很多"整体变慢"其实是排队。
5. **复制/刷盘尖峰**：`Innodb_buffer_pool_pages_dirty`、redo 写速率、大事务回放。
6. **缓存层失效**：Redis 集群异常导致回源打到 MySQL（看 `Com_select` 暴增 + 来源集中）。

**止血**：按定位结果回退变更 / 停掉抢资源的任务 / 杀扫描查询 / 临时提升规格。
**根治**：把"变更导致"的教训落到检测能力上（发布后自动看 Top digest 变化）。

---

## R5 单条 SQL 慢

直接转 **@SQL 体检**（有更完整的解释与索引判读手册）。应急期间的临时手段：
- [L1] 会话级 `FORCE INDEX`（写在 SQL 里，由发布生效）优于全局 `optimizer_switch` 改动。
- [L1] 应用侧加超时与熔断，避免拖垮连接池。
- [L2] 大结果集导出改从库 + 分批。

---

## R6 IO 打满 / 读延迟高

**确认**：`iostat -x 1 3`（`%util`、`r_await`、`aqu-sz`）；云看 IOPS/BPS 与规格上限；`Innodb_buffer_pool_reads` 与 `Innodb_os_log_written` 速率分别定位读/写放大。

**止血**
- [L2] 杀全表扫描/大排序查询（`Handler_read_rnd_next` 增速最快的会话）
- [L1] 停掉备份、`pt-table-checksum`、数据导出、大 `DELETE`
- 云：临时提升磁盘规格/IOPS（多数可在线生效）
- [L2] `SET GLOBAL innodb_io_capacity = <lower>;` 平滑刷盘（说明对脏页堆积的影响与回退值）

**根治**：索引修掉扫描放大；冷热分离/归档；`innodb_flush_method=O_DIRECT`（避免双重缓存，需重启，走 @变更评审）；`innodb_flush_log_at_trx_commit` 调整前必须讲清**丢数据风险**（改 2 = 主机崩溃可能丢 1s 事务，属 L3 级决策）。

---

## R7 主从延迟 / 疑似数据不一致

**判定**：`Seconds_Behind_Source` 大或 `NULL`；`Exec_Master_Log_Pos` 是否推进；`Replica_SQL_Running_State`。
```sql
SHOW REPLICA STATUS\G
SELECT CHANNEL_NAME,SERVICE_STATE,LAST_ERROR_MESSAGE FROM performance_schema.replication_connection_status;
```

**止血（按读依赖程度）**
1. 关键读切回主库/只读实例（应用开关，最快且零风险）。
2. 大事务导致：等待回放完成，**不要重启从库**（重启不清除积压，反而丢回放现场）。
3. [L1] 提升从库并行度（需停机窗口或用动态参数，8.0.26+ 视版本）：
```sql
STOP REPLICA SQL_THREAD;   -- [L1] 只停 SQL 线程，IO 线程继续收
SET GLOBAL replica_parallel_workers = 8;
SET GLOBAL replica_parallel_type = 'LOGICAL_CLOCK';
SET GLOBAL replica_preserve_commit_order = ON;
START REPLICA;
```
4. 从库规格不足：降从库上的分析任务/提升规格/加从库。
5. [L2] 若从库承担关键读且延迟不可接受：临时把该从库摘出流量（proxy/云权重调 0）。

**疑似不一致（严重，先停手判断）**
- **禁止**：`sql_replica_skip_counter` 跳事件、直接改从库数据"对齐"、在从库 `read_only=OFF`。
- 正确路径：确认是否丢事务（主库 binlog 完整性、半同步降级时间点）→ GTID 集合比对 → `pt-table-checksum` 在从库做只读校验（低峰，L2 有 IO 开销）→ 差异表用 `pt-table-sync --print` 先看再修 → 保留差异样本用于根因。
- 若判定为**逻辑 bug 造成的脏数据**：走 @备份恢复 的订正流程（影子表 + 可回滚），不要在主库手工 `UPDATE`。

---

## R8 磁盘不足 / 实例被锁为只读

**分类占比先看**：`du -sh /var/lib/mysql/* | sort -h | tail`；云看"数据/日志/临时文件"分项。

**按风险从低到高回收**
1. [L1] 关 general log：`SET GLOBAL general_log=OFF;`（先记录回退值）；大 slow log 轮转 `FLUSH SLOW LOGS;`（8.0）/ `FLUSH LOGS;` 后压缩归档，**不 rm 活跃文件**。
2. [L2] `PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY;` —— **前置检查必须有**：所有从库 `Relay_Source_Log_File` / `Read_Master_Log_Pos` 已越过保留位点，且下游同步任务（DTS/Canal/Kafka）位点也已越过。漏检等于打断数据链路。
3. [L1] `SET GLOBAL binlog_expire_logs_seconds = 259200;`（动态生效，说明对下游的影响）
4. [L2] 归档/清理历史数据：分批 `DELETE ... LIMIT 1000` 循环（避免大事务撑爆 undo 与复制延迟），或 `pt-archiver`。空间**不会**立即归还 OS，需评估后续重建。
5. 云：扩容磁盘（多数在线，最快止血），扩完再治理。
6. `lsof +L1 | grep mysql` 检查已删除但句柄未释放的空间（tmp 表、旧 binlog）——这是"明明删了空间不回来"的标准答案。

**禁止**：`rm` 数据文件 / undo / `ib_logfile` / `#sql-*`；空间紧张时 `OPTIMIZE TABLE`（需额外临时空间，可能反向撑爆）。
**根因**：增长斜率没被监控（→ 改进检测项：磁盘增长预测告警）、无归档策略、备份文件落本机、大事务未治理。

---

## R9 内存告警 / OOM

**确认**：`dmesg -T | grep -i -E 'oom|killed'`；错误日志 `Got signal 9` / `Out of memory`；总账公式：
`BP + (sort+join+read+read_rnd+thread_stack) × 峰值连接 + perf_schema + OS page cache`

**止血**
- 回收异常会话（尤其 `Sorting`/`Sending data` 且 `time` 大的）
- [L2] 降 `max_connections`（需评估应用侧能否容忍排队）或降会话 buffer：`SET GLOBAL sort_buffer_size=<small>;`（注意仅对新连接生效的会话变量，全局值是默认值）
- [L2] 必要时下调 BP：`SET GLOBAL innodb_buffer_pool_size=<smaller>;` —— 命中率会掉、IO 会涨，属两害相权，说明观察指标
- 加内存 / 拆实例（根治）

**根治**：内存总账写进巡检；`swappiness=1`；THP `never`；`performance_schema` 上限；BP 实例数与 chunk 对齐。

---

## R10 实例崩溃 / 无法启动 / 疑似数据损坏

**第一动作永远是读错误日志**，不是重启：
```bash
tail -500 "$(mysql -sN -e 'SELECT @@log_error' 2>/dev/null | tail -1)" \
  || tail -500 /var/log/mysqld.log
```
关键线索：`Assertion failure`、`Page check sum`、`Database was not shutdown normally`、`Could not open ... tablespace`、`Discarding OS file handles`、具体栈与函数名。

**分支处理**
1. **异常关机后正常恢复中**（看到 `redo log was scanned up to LSN ...`、恢复进度）→ **等待**，不要多次重启（每次重启恢复从头计时）。观察错误日志推进。
2. **恢复失败/启动即崩** → [L3 高危] 逐级 `innodb_force_recovery` 1→2→3→4→5→6
   - **前置（强制）**：先做文件级冷备（`cp -a` datadir 到另一块盘），每个 force level 尝试前都要能退回。
   - 目标只有一个：**起来后立刻 `mysqldump`/`SELECT INTO OUTFILE` 抢救可访问的表**，然后重建实例导入。
   - 说明：level ≥3 可能永久损坏数据；只读保护（`innodb_read_only`）在 ≥4 生效；期间禁止任何写入。
   - ⚠️ 必须"业务与管理层确认"后才执行。
3. **表空间缺失/单表损坏**（`Table './db/tbl' is marked as crashed`、`Cannot find tablespace`）→ 先 dump 该表结构，尝试重建表 + 从备份恢复该表（通用表空间可单表恢复），或 `DISCARD/IMPORT TABLESPACE` 从备份导入（需表结构一致）。
4. **权限/配置导致起不来**：`ls -lZ` datadir 属主、AppArmor/SELinux、磁盘只读挂载、`lower_case_table_names` 与既有数据不匹配、`innodb_log_file_size` 被改但旧文件还在（8.0.30+ 已缓解）。
5. **主库崩溃需切换**：
   - 先比对候选从库的 `Relay_Source_Log_File`/`Exec_Master_Log_Pos`/`gtid_executed`，选**已应用最多**的；
   - ⚠️ 明确可能丢失的事务区间（异步复制必然有窗口；半同步降级期间同理），把"丢多少"算出来给业务确认；
   - 切换后：原主库回来必须以从库身份加入并校验，防止"双主写"造成不可挽回的冲突；
   - 应用连接串/DNS/Proxy 收敛与只读保护（`super_read_only` 打开原主）。

**恢复后必做**：数据一致性校验（关键表行数、校验和、业务对账）、错误日志留档、根因归类（硬件/内核 Bug/数据损坏/人为）、把"是否有可用备份 + 是否演练过"写进复盘。

---

## 通用应急检查表（贴在作战文档顶部）

- [ ] 现场已采集（R0 快照命令跑过）
- [ ] 时间点已对齐（变更/发布/备份/定时任务/HA 事件）
- [ ] 影响面已量化（哪些库表、多少请求、是否有资损）
- [ ] 拓扑与数据链路已确认（从库、DTS/Canal、下游数仓）
- [ ] 每个止血动作都有回退命令
- [ ] 涉及丢数据风险的决策已升级确认
- [ ] 临时措施已登记（负责人 + 回退期限）
- [ ] 复盘时间已约定（24–48h 内）
