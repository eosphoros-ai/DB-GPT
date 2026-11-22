# 现象 → 根因决策树

每棵树的固定结构：**先分层定位（是哪一层）→ 再收敛（是哪个对象）→ 止血 → 根因归类**。
按顺序执行，不要跳步——多数误判来自没做分层就直接优化 SQL。

---

## T1 CPU 使用率高

1. **区分态**：`top`/`vmstat` 看是 `us` 高还是 `sy`/`wa` 高。
   - `wa` 高 → 转 T6（IO 瓶颈），不是 CPU 问题。
   - `sy` 高 → 查连接风暴（`Aborted_connects` 速率）、频繁线程创建（`thread_cache_size` 过小）、大量小事务 fsync。
2. `us` 高 → **定位对象**：`SHOW FULL PROCESSLIST` 或 `performance_schema.events_statements_current`，按 `TIME` 与 `CPU` 排序找活跃长查询。
3. 判断是**单条 SQL** 还是**量变**：
   - 单条 → `EXPLAIN`。`type=ALL`/`rows` 巨大/`Extra` 含 `Using filesort; Using temporary` → 全表扫描+排序分组。
   - 量变（QPS 涨）→ 看 `Questions` 增量与来源 IP 分布，是缓存失效/大促/上游重试。
4. **止血**：`KILL <id>`（先杀 `TIME` 最大的只读 SELECT；DML 需评估回滚耗时）；限流来源；临时加大 `thread_pool` 或降并发。
5. **根因归类**：缺索引 / SQL 写法（函数包列、隐式转换、`OR`、前导 `%`）/ 统计信息失真 / 流量突增 / 缓存击穿。

**易错点**：CPU 高时盲目加 `innodb_buffer_pool_size` 无用；重启实例只是把问题延后且丢掉现场。

---

## T2 连接数打满 / Too many connections

1. 先看 `Threads_connected / max_connections` 与 `Threads_running`。
2. **`Threads_running` 也高** → 慢 SQL 拖住连接。转 T1 处理慢查询，连接自然释放。
3. **`Threads_running` 低但 connected 高** → 连接泄漏/池配置过大。
   - `SELECT SUBSTRING_INDEX(host,':',1) ip, USER, COUNT(*) FROM information_schema.processlist GROUP BY 1,2 ORDER BY 3 DESC` 找异常来源。
   - 大量 `Sleep` 且 `TIME` 很长 → `wait_timeout` 未生效或池 `maxActive` 过大/未配 `minEvictableIdleTime`。
4. **止血**：留出管理连接（8.0 用 `ADMIN_ADDRESS`/`extra_port`；5.7 用 `extra_max_connections`）。批量 `SELECT CONCAT('KILL ',id,';') FROM ... WHERE COMMAND='Sleep' AND TIME>600` 生成清单，人工确认后执行。适度上调 `max_connections`（内存允许时，注意每连接内存）。
5. **根因归类**：连接池未设上限/未回收 / 慢 SQL 占用 / 应用重启风暴 / `wait_timeout` 与池 `idleTimeout` 不匹配（表现为 `Communications link failure`）。

---

## T3 锁等待与死锁

1. **先看是哪类锁**：
   - 行锁：`Innodb_row_lock_current_waits > 0`，`trx_isolation` 下等待。
   - MDL 元数据锁：processlist 大量 `Waiting for table metadata lock` → 几乎都是**未提交事务 + DDL** 组合。
   - 表锁：`Table_locks_waited` 增长 → MyISAM、`LOCK TABLES`、部分 DDL。
2. **行锁定位**（8.0）：
   - `performance_schema.data_lock_waits` 找 `BLOCKING_ENGINE_TRANSACTION_ID`；
   - 关联 `data_locks` + `information_schema.innodb_trx` 拿到持锁 SQL、持锁时长、连接。
   - 5.7：`information_schema.innodb_lock_waits` + `innodb_trx`。
3. **止血**：优先让**持锁方**提交/回滚（业务确认），而不是杀等待方——杀等待方只会换个位置等。持锁方无法联系时才 `KILL`，并预估其事务回滚耗时（大事务回滚可能比等更久）。
4. **死锁**：`SHOW ENGINE INNODB STATUS` 的 `LATEST DETECTED DEADLOCK` 段读事务 SQL 与持有/等待的锁；`performance_schema.events_statements_history` 补充上下文。
5. **根因归类**：事务过大/过长（含 RPC 外呼）/ 更新顺序不一致（交叉更新）/ 唯一索引冲突导致 S 锁升级为 X / 无索引导致锁范围放大（间隙锁）/ DDL 撞长事务。
6. **反查长事务**：`SELECT trx_id, trx_started, TIMESTAMPDIFF(SECOND,trx_started,NOW()) dur, trx_rows_modified, id FROM information_schema.innodb_trx ORDER BY trx_started LIMIT 20`。

---

## T4 慢查询整体变多

1. **确认是"变慢"还是"变多"**：QPS 未涨而延迟涨 → 环境变化；QPS 涨 → 容量。
2. **找环境变化**（按发生概率排）：
   - 统计信息被重算 / `ANALYZE TABLE` 刚跑 → 执行计划跳变；
   - 数据量跨过临界点（原本走索引的现在回表成本更高）；
   - 新参数/新拓扑（主从切换、BP 被调小）；
   - 资源被抢占（同机其他进程、云 RDS 规格/IO 突发额度耗尽）；
   - 刷脏/Checkpoint 尖峰（`Innodb_buffer_pool_pages_dirty` 与 redo 写速率）；
   - 复制大事务、备份任务（xtrabackup 读盘）撞上业务高峰。
3. **定位 Top SQL**：`performance_schema.events_statements_summary_by_digest` 按 `SUM_TIMER_WAIT` / `AVG_TIMER_WAIT` 排序（注意与业务高峰时间对齐，`first_seen`/`last_seen`）。或解析慢日志（`pt-query-digest`）。
4. **逐条转 T1/T5** 做单 SQL 归因。

---

## T5 单条 SQL 慢

1. `EXPLAIN`（8.0 加 `FORMAT=TREE`，必要时 `EXPLAIN ANALYZE`——**注意它会真执行，DML 必须在从库/影子库**）。
2. 逐项检查失效原因清单（详见 SQL 体检技能的 index-playbook）：
   - 列上有函数/运算/隐式类型转换（`varchar` 列传数字）；
   - 字符集/排序规则不一致导致连接列无法用索引；
   - 不满足最左前缀；范围条件右边索引列失效；
   - `OR` / `NOT IN` / `<>` / 前导 `%` / `SELECT *`；
   - `ORDER BY`/`GROUP BY` 与索引顺序不匹配 → `Using filesort`；
   - 深度分页 `LIMIT 1000000,20`；
   - 大 `IN` 列表 / 子查询物化；
   - 驱动表选错（连接顺序）；
   - 统计信息不准（`rows` 估算与实际差数量级）；
   - 索引区分度低（`Cardinality` 太小）；
   - 回表次数过多（覆盖索引可解）。
3. 验证方式：加 `FORCE INDEX` 对比、拆开子查询、缩小时间范围二分定位、看 `Handler_read_*` 前后差。

---

## T6 IO 瓶颈 / 读延迟高

1. `iostat -x 1`：`%util`、`await`、`r/s`、`w/s`、`avgqu-sz`。云 RDS 看监控 IOPS/BPS 与规格上限。
2. 分层：
   - **读放大**：`Innodb_buffer_pool_reads` 突增 → BP 命中率下降（大表扫描污染 / BP 太小 / 冷启动）。
   - **写放大**：`Innodb_os_log_written`、`Innodb_data_writes` 突增 → 批量大事务、刷脏策略（`innodb_io_capacity` 与实际盘能力不匹配）、`innodb_flush_log_at_trx_commit` 设置。
   - **空间**：磁盘接近满 → 文件系统预留与自动扩展；`tmpfile` 因大排序撑爆磁盘。
3. **止血**：杀掉扫描型查询；降并发；把备份/分析任务错峰；临时提升云盘规格/IOPS；`SET GLOBAL innodb_io_capacity` 谨慎下调以让刷盘平滑。
4. **根因归类**：容量不足 / 无索引全表扫描 / 冷热未分离（历史数据未归档）/ 盘与参数不匹配 / 混部争抢。

---

## T7 主从延迟

1. 先看 `Seconds_Behind_Source`（注意 SQL 单线程时该值含义）与 `Exec_Master_Log_Pos` 是否推进。
2. **判断方向**：
   - 延迟但无业务影响读从库 → 优先级降；
   - 延迟且从库承载读流量 → 需立刻处理（可能读到旧数据、切换会丢数据）。
3. **定位模式**：
   - **单点尖峰后回落** → 大事务（一次改百万行的 DML、`OPTIMIZE`、无 where 更新）在从库串行回放。查主库 `binlog` 大事务、`General/慢日志`、变更工单。
   - **持续增长** → 从库能力不足（从库配置低/IO 差/单机承载多个从库/从库上还跑分析查询）。
   - **DDL 导致** → `ALTER` 在主库执行完才开始回放，从库需重放同等时间。大表 DDL 必须错峰或用 gh-ost/pt-osc。
   - **参数差异** → 从库 `innodb_flush_log_at_trx_commit=2`/`sync_binlog=1000` 才是合理的，从库 `read_only` 与并行 worker=0 会明显变慢。
   - **网络/断链** → `Last_IO_Error` 1236（binlog 被清理）、连接超时。
4. **止血**：开/加大并行复制（`replica_parallel_type=LOGICAL_CLOCK`、`replica_parallel_workers`，8.0.26+ `replica_preserve_commit_order`）；把关键读切回主库或只读实例；提升从库规格；暂停从库上的非必要任务；极端情况用 `pt-table-sync` 前先确认数据安全。
5. **禁忌**：`sql_replica_skip_counter` 跳过事件在 GTID 下不可用且可能造成不一致；`SET GLOBAL read_only=OFF` 到从库写入是重大红线。

---

## T8 磁盘空间不足

1. **先分类占用于**：数据（`information_schema.tables` 汇总）、binlog（`SHOW BINARY LOGS`）、undo（长事务/大量回滚段膨胀）、tmp（大排序/`innodb_tmpfile` 或 `ibtmp1`）、慢日志/general log/错误日志、core dump、备份文件留在本机。
2. **立刻可回收**（低风险顺序）：
   - 关闭 `general_log`、清理超大慢日志（先备份后 `FLUSH SLOW LOGS`/`FLUSH ERROR LOGS` 轮转，勿 `rm` 活跃文件）；
   - `PURGE BINARY LOGS TO`（确认所有从库/minio/Kafka 位点已越过）；
   - 调小 `binlog_expire_logs_seconds`；
   - 归档/删除历史数据（分批 `DELETE` + 低峰，或 `pt-archiver`）；
   - `innodb_truncate_encrypted` 之类不适用，undo 膨胀需等长事务结束。
3. **需要评估**：`OPTIMIZE TABLE`/重建表回收碎片（会持锁或占大量临时空间——**空间已紧张时禁止**，可能反向撑爆）。
4. **云 RDS**：磁盘到阈值会被锁定为只读；先扩容或清理 binlog，再排查增长原因。
5. **禁忌**：绝不 `rm` 数据目录文件、绝不手工删 `ibdata`/`ib_logfile`/undo 表空间。

---

## T9 内存告警 / OOM

1. **算总账**：`BP 总量 + (join_buffer + sort_buffer + read_buffer + read_rnd_buffer + thread_stack) × 峰值连接数 + 其他进程` vs 物理内存。
2. **常见元凶**：
   - `max_connections` 配过大 + 会话 buffer 过大（`sort_buffer_size` 设成 GB 级是典型错误）；
   - BP 设超过物理内存 75%（独占机器）/ 60%（多实例混部）；
   - 单条大结果集（`mysql` 客户端 `--quick`/`useSSL` 无关，服务端 `net_buffer_length`/结果物化）；
   - `performance_schema` 开销（内存小的机器，`max_performance_schema_memory`）；
   - 页缓存 + THP。
3. **止血**：降并发上限、回收异常会话、临时下调 BP（会引发命中率下降，属两害相权）；必要时给实例加内存或拆分。
4. **确认**：`dmesg | grep -i oom`、错误日志中 `Got signal 9`/`Out of memory`；云 RDS 看事件与重启记录。

---

## T10 实例不可用 / 反复重启 / 无法启动

1. **看错误日志**（这是第一优先，不是重启）：`Got signal`、`InnoDB: Database was not shutdown normally!`、`Page check sum`、`Assertion failure`、`Discarding OS file handles`、崩溃栈。
2. **区分**：
   - **崩溃后恢复中** → 等待 `innodb_force_recovery=0` 自然恢复；不要随意重启多次（每次延长恢复时间）。
   - **恢复失败** → 逐级 `innodb_force_recovery` 1→6（**每级都必须先做物理备份**；≥3 有数据损坏风险；启动后立即 `mysqldump`/`SELECT INTO OUTFILE` 抢救表，然后重建实例）。
   - **参数/文件权限导致起不来** → `ls -l` datadir、`AppArmor/SELinux`、磁盘只读、`/var/lib/mysql` 空间、`lower_case_table_names` 与已有数据不匹配。
   - **主库崩溃需要 HA 切换** → 确认 binlog 是否完整（半同步降级/异步会丢事务）、GTID 集比对、选择切换目标、应用侧读写分离收敛。
3. **数据校验**：恢复后 `pt-table-checksum`（有条件时）、比对关键表行数/校验和、比对 GTID 集合与 binlog 位点。
4. **禁忌**：未做物理备份前不做任何 `innodb_force_recovery` 与 `DROP`/`OPTIMIZE`；不删 `#sql-*` 中间表文件（Online DDL 残留）直到确认无回滚需要。

---

## 通用归因优先级（现象不明时按此顺序排除）

`资源（CPU/IO/内存/磁盘）` → `锁与事务` → `执行计划/索引` → `流量与热点` → `配置与参数漂移` → `拓扑与复制` → `版本/内核 Bug（查 Release Notes 与错误码）`

## 时间线证据法（复盘必备）

结论必须能挂到时间点上。最小采集集：错误日志、慢日志、`SHOW GLOBAL STATUS` 周期快照（或监控曲线）、变更/发布记录、流量曲线、主从切换事件。**先对齐时间轴，再谈因果。**
