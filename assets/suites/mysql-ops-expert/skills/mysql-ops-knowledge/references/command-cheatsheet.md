# 只读诊断命令清单

按场景分组。**全部为只读或低风险命令**，可直接给用户复制执行。含 5.7 / 8.0 差异标注。

约定：需要采集数据时，**一次给全一组命令**（用户讨厌来回追问），并注明"请在从库执行"或"主库/从库各执行一次"。

## 0. 基础信息采集（任何诊断的第一步）

```sql
SELECT VERSION(), @@version_comment;
SHOW GLOBAL VARIABLES WHERE Variable_name IN
 ('version','version_compile_machine','character_set_server','collation_server',
  'innodb_buffer_pool_size','innodb_buffer_pool_instances','max_connections',
  'innodb_log_file_size','innodb_log_files_in_group','innodb_redo_log_capacity',
  'innodb_flush_log_at_trx_commit','sync_binlog','innodb_io_capacity',
  'innodb_io_capacity_max','transaction_isolation','sql_mode','read_only',
  'super_read_only','log_bin','binlog_format','gtid_mode','enforce_gtid_consistency',
  'lower_case_table_names','skip_name_resolve','open_files_limit','table_open_cache',
  'sort_buffer_size','join_buffer_size','tmp_table_size','max_heap_table_size',
  'wait_timeout','interactive_timeout','long_query_time','slow_query_log',
  'innodb_flush_method','innodb_file_per_table','innodb_purge_threads',
  'replica_parallel_workers','slave_parallel_workers','binlog_row_image');
SHOW GLOBAL STATUS;              -- 全量快照，便于两次做差
SHOW ENGINE INNODB STATUS\G      -- 锁/事务/刷盘/history list 一屏看全
```

```bash
mysql -e "SHOW GLOBAL STATUS" > status_$(date +%H%M%S).txt   # 间隔 10s 采两次算速率
uptime; vmstat 1 5; iostat -x 1 3; df -hT; ls -l /var/lib/mysql | head -50
nproc; free -g; cat /sys/kernel/mm/transparent_hugepage/enabled
```

## 1. 会话与连接

```sql
-- 8.0.22+ 推荐
SELECT * FROM performance_schema.threads WHERE PROCESSLIST_ID IS NOT NULL;
SHOW FULL PROCESSLIST;   -- 注意 SHOW FULL 才看得到完整 SQL 与 Host

-- 按来源/用户聚合找连接泄漏
SELECT SUBSTRING_INDEX(host,':',1) AS ip, user, db, command, COUNT(*) AS cnt
FROM information_schema.processlist GROUP BY 1,2,3,4 ORDER BY cnt DESC;

-- 跑了超过 5 秒的查询
SELECT id,user,db,command,time,state,LEFT(info,200) AS sql_head
FROM information_schema.processlist
WHERE command<>'Sleep' AND time>5 ORDER BY time DESC;

-- 超过 60s 的 Sleep（生成清理清单，人工确认后再执行 KILL）
SELECT CONCAT('KILL ',id,'; -- slept ',time,'s from ',host) AS cmd
FROM information_schema.processlist
WHERE command='Sleep' AND time>60 ORDER BY time DESC LIMIT 50;
```

## 2. 锁与事务

```sql
-- 8.0
SELECT r.trx_mysql_thread_id AS waiting_thd, r.trx_query AS waiting_sql,
       b.trx_mysql_thread_id AS blocking_thd, b.trx_query AS blocking_sql,
       b.trx_started, TIMESTAMPDIFF(SECOND,b.trx_started,NOW()) AS blocking_sec
FROM performance_schema.data_lock_waits w
JOIN information_schema.innodb_trx r ON r.trx_id = w.REQUESTING_ENGINE_TRANSACTION_ID
JOIN information_schema.innodb_trx b ON b.trx_id = w.BLOCKING_ENGINE_TRANSACTION_ID;

-- 5.7（8.0 已移除 innodb_locks / innodb_lock_waits）
SELECT r.trx_mysql_thread_id waiting_thd, b.trx_mysql_thread_id blocking_thd,
       r.trx_query, b.trx_query
FROM information_schema.innodb_lock_waits w
JOIN information_schema.innodb_trx r ON r.trx_id=w.requesting_trx_id
JOIN information_schema.innodb_trx b ON b.trx_id=w.blocking_trx_id;

-- 长事务 / 大事务（最常被忽略的一屏）
SELECT trx_id, trx_state, trx_started,
       TIMESTAMPDIFF(SECOND,trx_started,NOW()) AS dur_sec,
       trx_mysql_thread_id AS thd, trx_rows_locked, trx_rows_modified,
       LEFT(trx_query,120) AS q
FROM information_schema.innodb_trx
ORDER BY trx_rows_modified DESC, dur_sec DESC;

-- 未开启事务但连接挂着（客户端忘 commit，同样持 MDL）
SELECT * FROM sys.session WHERE command='Sleep' AND time>60;   -- 需 sys schema

-- 死锁原文
SHOW ENGINE INNODB STATUS\G   -- 看 LATEST DETECTED DEADLOCK 段
```

## 3. SQL 性能

```sql
-- Top 累计耗时（注意：自实例启动或 truncate 起累计，需结合 last_seen）
SELECT SCHEMA_NAME, DIGEST_TEXT, COUNT_STAR,
       ROUND(AVG_TIMER_WAIT/1e12,3) AS avg_sec,
       ROUND(SUM_TIMER_WAIT/1e12,1) AS total_sec,
       SUM_ROWS_SENT, SUM_ROWS_EXAMINED,
       ROUND(SUM_ROWS_EXAMINED/GREATEST(COUNT_STAR,1),0) AS examined_per_exec,
       FIRST_SEEN, LAST_SEEN
FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC LIMIT 20;

-- 全表扫描 / 磁盘临时表 / 文件排序最多的语句
SELECT DIGEST_TEXT, COUNT_STAR, SUM_NO_INDEX_USED, SUM_CREATED_TMP_DISK_TABLES,
       SUM_SORT_MERGE_PASSES
FROM performance_schema.events_statements_summary_by_digest
WHERE SUM_NO_INDEX_USED>0 ORDER BY SUM_TIMER_WAIT DESC LIMIT 15;

-- 单 SQL 前后 IO 计数对比（判断索引是否真生效）
FLUSH STATUS; SELECT ... ; SHOW SESSION STATUS LIKE 'Handler%';

-- 统计信息是否失真
SELECT * FROM mysql.innodb_table_stats WHERE table_name='t';
SELECT * FROM mysql.innodb_index_stats WHERE table_name='t' AND stat_name='n_leaf_pages';
```

```sql
-- 执行计划（8.0）
EXPLAIN FORMAT=TREE SELECT ...;      -- 可读性最好
EXPLAIN ANALYZE SELECT ...;          -- 真执行：只用于 SELECT，且优先从库
EXPLAIN FORMAT=JSON SELECT ...;      -- 需要 cost 细节时
SHOW WARNINGS;                       -- 配合 EXPLAIN 看优化器改写
```

```bash
pt-query-digest /var/log/mysql/slow.log --limit 10 --since '2h'
mysqldumpslow -s c -t 10 /var/log/mysql/slow.log   # 无 pt 工具时
```

## 4. 索引与容量

```sql
-- 大表 Top20（含碎片与自增余量线索）
SELECT table_schema, table_name, engine, table_rows,
  ROUND(data_length/1024/1024/1024,2) AS data_gb,
  ROUND(index_length/1024/1024/1024,2) AS idx_gb,
  ROUND(data_free/1024/1024/1024,2) AS free_gb,
  ROUND(data_free/GREATEST(data_length+index_length,1),3) AS frag_ratio,
  ROW_FORMAT, table_collation, create_time, update_time
FROM information_schema.tables
WHERE table_schema NOT IN ('mysql','information_schema','performance_schema','sys')
ORDER BY data_length+index_length DESC LIMIT 20;

-- 冗余/未使用索引
SELECT * FROM sys.schema_redundant_indexes;
SELECT * FROM sys.schema_unused_indexes;             -- 自启动累计，别只看一次
SELECT * FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE index_name IS NULL AND count_star>0 ORDER BY sum_timer_wait DESC; -- 全表扫热点

-- 无主键 / 大列 / char 滥用（影响复制与在线 DDL）
SELECT t.table_schema,t.table_name FROM information_schema.tables t
LEFT JOIN information_schema.statistics s
  ON s.table_schema=t.table_schema AND s.table_name=t.table_name AND s.index_name='PRIMARY'
WHERE t.table_type='BASE TABLE' AND t.table_schema NOT IN ('mysql','sys') AND s.index_name IS NULL;

-- 自增溢出风险
SELECT table_schema,table_name,column_name,column_type,extra,
       ROUND(AUTO_INCREMENT / (CASE data_type
         WHEN 'tinyint' THEN 127 WHEN 'smallint' THEN 32767
         WHEN 'int' THEN 2147483647 WHEN 'bigint' THEN 9223372036854775807 END),4) AS used_ratio
FROM information_schema.columns c JOIN information_schema.tables t USING(table_schema,table_name)
WHERE extra LIKE '%auto_increment%' HAVING used_ratio>0.5;

-- 索引区分度（判断索引是否值得建）
SELECT INDEX_NAME, CARDINALITY, TABLE_ROWS,
       ROUND(CARDINALITY/GREATEST(TABLE_ROWS,1),4) AS selectivity
FROM information_schema.STATISTICS WHERE TABLE_NAME='t' AND TABLE_SCHEMA='db';
```

## 5. 复制

```sql
SHOW REPLICA STATUS\G      -- 8.0.22+；旧版 SHOW SLAVE STATUS\G
SHOW BINARY LOG STATUS;    -- 8.0.24+；旧版 SHOW MASTER STATUS

-- 延迟趋势（连续采样，别信单次值）
SELECT NOW(), replica_server_uuid, source_host,
       seconds_behind_source, replica_sql_running, replica_io_running
FROM performance_schema.replication_applier_status_by_worker; -- 8.0

SELECT CHANNEL_NAME, SERVICE_STATE, LAST_ERROR_MESSAGE, LAST_ERROR_TIMESTAMP
FROM performance_schema.replication_connection_status;
SELECT CHANNEL_NAME, APPLIED_TRANSACTION,
       TIMESTAMPDIFF(SECOND,ORIGINAL_COMMIT_TIMESTAMP,APPLIED_TIMESTAMP) AS lag_sec
FROM performance_schema.replication_applier_status_by_worker;

-- GTID 主从比对
SELECT @@gtid_executed;
SELECT GTID_SUBSET(slave_set, master_set);   -- 0 表示从库有主库没有的事务（危险）
```

## 6. 空间与日志

```sql
SHOW BINARY LOGS;
SHOW RELAYLOG EVENTS IN 'relay-bin.000001' LIMIT 20;   -- 从库回放内容
SELECT @@binlog_expire_logs_seconds, @@expire_logs_days;
PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY;  -- 写操作：需确认所有下游位点

SELECT file_name, ROUND(total_extents*extent_size/1024/1024/1024,2) AS undo_gb
FROM information_schema.innodb_undo_tablespaces;    -- 8.0
```

```bash
du -sh /var/lib/mysql/* | sort -h | tail -20
lsof +L1 | grep mysql          # 已删除但句柄未释放的空间（常被忽略）
```

## 7. 备份与恢复前校验

```bash
xtrabackup --version
innobackupex --version 2>/dev/null
# 备份集可用性
xtrabackup --prepare --apply-log-only --target-dir=/data/backup   # 输出必须含 completed OK
mysqlbinlog --no-defaults --base64-output=decode-rows -vv binlog.000123 | head -200
mysqlbinlog --start-datetime='2026-10-27 10:00:00' --stop-datetime='2026-10-27 10:05:00' \
  --database=db binlog.000123 > /tmp/recover.sql
mysql --defaults-file=... -e "SELECT COUNT(*) FROM db.tbl"   # 误删后确认影响行数
```

## 8. 参数与运行时值

```sql
-- 运行时值 vs 配置文件值（排查"改了没生效"）
SELECT a.VARIABLE_NAME, a.VARIABLE_VALUE AS runtime,
       b.VARIABLE_VALUE AS config_file_value
FROM performance_schema.global_variables a
LEFT JOIN performance_schema.variables_info b USING(VARIABLE_NAME)
WHERE a.VARIABLE_NAME LIKE 'innodb%';

-- 动态可改 vs 需重启
SELECT VARIABLE_NAME, VARIABLE_SOURCE, SET_TIME, SET_USER FROM performance_schema.variables_info
WHERE VARIABLE_SOURCE<>'COMPILED';
```

```bash
mysqld --verbose --help 2>/dev/null | grep -A2 '^Variables'
grep -RIn '^[^#]' /etc/my.cnf /etc/mysql/ 2>/dev/null      # 实际生效的配置行
mysqld --print-defaults                                     # 配置文件解析后的参数
mysql -e "SELECT @@datadir, @@log_error, @@slow_query_log_file, @@general_log_file, @@pid_file\G"
```

## 9. 云上受限环境的替代取数

无 OS 权限时，用这些替代：
- 磁盘/IOPS/连接/CPU → 云监控 `DescribeDBInstancePerformance`（或控制台曲线导出 CSV，交给套件分析）。
- 慢日志明细 → 控制台"慢日志明细/SQL 洞察"导出。
- 无法 `SHOW ENGINE INNODB STATUS` → 用 `information_schema.innodb_trx` + 监控锁等待指标。
- 参数 → 云"参数模板"导出 JSON 交给参数调优技能。
