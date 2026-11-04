# 巡检清单与采集 SQL

全部为 🟢 L0 只读命令。**建议主库、从库各执行一次**（复制类与负载类指标必须分开看）。
`SHOW GLOBAL STATUS` 类累计计数器需**间隔 30–60s 采两次做差**。

## 采集包（直接给用户）

```bash
#!/bin/bash
# patrol.sh — MySQL 只读巡检采集包。用法: ./patrol.sh <host> <port> <user>
set -euo pipefail
H=${1:-127.0.0.1}; P=${2:-3306}; U=${3:-patrol_ro}
TS=$(date +%Y%m%d_%H%M%S); OUT="patrol_${H}_${TS}"; mkdir -p "$OUT"; cd "$OUT"
M="mysql -h$H -P$P -u$U -p --comments -A"

# 0. 环境与身份
$M -e "SELECT VERSION() v, @@hostname hn, @@datadir d, @@log_error le, \
 @@slow_query_log_file sq, @@read_only ro, @@super_read_only sro, @@server_id sid\G" > 00_env.txt
$M -e "SHOW GLOBAL VARIABLES" > 01_vars.txt
$M -e "SHOW GLOBAL STATUS"     > 02_status_t1.txt; sleep 60
$M -e "SHOW GLOBAL STATUS"     > 03_status_t2.txt
$M -e "SHOW ENGINE INNODB STATUS\G" > 04_innodb_status.txt
$M -e "SHOW BINARY LOG STATUS\G" 2>/dev/null || $M -e "SHOW MASTER STATUS\G" > 05_binlog.txt
$M -e "SHOW REPLICA STATUS\G" 2>/dev/null || $M -e "SHOW SLAVE STATUS\G" > 05_repl.txt

# 1. 连接与会话
$M -e "SHOW FULL PROCESSLIST" > 10_processlist.txt
$M -Ase "SELECT SUBSTRING_INDEX(host,':',1) ip,user,db,command,STATE,COUNT(*) c,
   MAX(time) max_t, SUM(time) sum_t FROM information_schema.processlist
   GROUP BY 1,2,3,4,5 ORDER BY c DESC LIMIT 100" > 11_conn_by_src.txt

# 2. 锁与事务
$M -e "SELECT * FROM information_schema.innodb_trx ORDER BY trx_started" > 20_trx.txt
$M -e "SELECT * FROM performance_schema.data_lock_waits" > 21_lock_waits.txt 2>/dev/null \
 || $M -e "SELECT * FROM information_schema.innodb_lock_waits" > 21_lock_waits.txt
$M -e "SELECT * FROM performance_schema.metadata_locks WHERE LOCK_STATUS='PENDING'" > 22_mdl.txt

# 3. SQL 性能 Top
$M -e "SELECT SCHEMA_NAME,DIGEST_TEXT,COUNT_STAR,ROUND(SUM_TIMER_WAIT/1e12,1) total_s,
  ROUND(AVG_TIMER_WAIT/1e9,1) avg_ms,SUM_ROWS_EXAMINED,SUM_ROWS_SENT,SUM_NO_INDEX_USED,
  SUM_CREATED_TMP_DISK_TABLES,SUM_SORT_MERGE_PASSES,LAST_SEEN
  FROM performance_schema.events_statements_summary_by_digest
  ORDER BY SUM_TIMER_WAIT DESC LIMIT 30" > 30_top_digest.txt
$M -e "SELECT NAME,VARIABLE_VALUE FROM performance_schema.global_status
  WHERE VARIABLE_NAME LIKE 'Innodb%' OR VARIABLE_NAME LIKE 'Select%'
     OR VARIABLE_NAME LIKE 'Sort%' OR VARIABLE_NAME LIKE 'Created_tmp%'
     OR VARIABLE_NAME LIKE 'Table%'" > 31_key_status.txt

# 4. 空间与对象风险
$M -e "SELECT table_schema,ROUND(SUM(data_length+index_length)/1024/1024/1024,2) gb,
  ROUND(SUM(data_free)/1024/1024/1024,2) free_gb,COUNT(*) tables_n
  FROM information_schema.tables GROUP BY 1 ORDER BY 2 DESC" > 40_schema_size.txt
$M -Ase "SELECT table_schema,table_name,engine,ROUND((data_length+index_length)/1024/1024,1) mb
   FROM information_schema.tables
   WHERE engine NOT IN ('InnoDB') AND table_schema NOT IN ('mysql','sys','performance_schema')
   ORDER BY data_length+index_length DESC LIMIT 30" > 40b_non_innodb.txt
$M -Ase "SELECT table_schema,table_name,ROUND((data_length+index_length)/1024/1024/1024,2) gb,
   ROUND(data_free/GREATEST(data_length+index_length,1),3) frag,table_rows,create_time
   FROM information_schema.tables
   WHERE table_schema NOT IN ('mysql','sys','information_schema','performance_schema')
   ORDER BY data_length+index_length DESC LIMIT 30" > 41_top_tables.txt
$M -Ase "SELECT t.table_schema,t.table_name,
   ROUND((t.data_length+t.index_length)/1024/1024/1024,2) gb
   FROM information_schema.tables t
   LEFT JOIN information_schema.statistics s
     ON s.table_schema=t.table_schema AND s.table_name=t.table_name AND s.index_name='PRIMARY'
   WHERE t.table_type='BASE TABLE'
     AND t.table_schema NOT IN ('mysql','sys','information_schema','performance_schema')
     AND s.index_name IS NULL GROUP BY 1,2 ORDER BY gb DESC" > 42_no_pk.txt
$M -Ase "SELECT table_schema,table_name,column_name,column_type,auto_increment
   FROM information_schema.columns c JOIN information_schema.tables t USING(table_schema,table_name)
   WHERE extra LIKE '%auto_increment%' AND data_type IN ('int','smallint','mediumint','tinyint')" > 43_autoinc.txt
$M -Ase "SELECT table_schema,table_name,column_name,data_type,character_set_name,collation_name
   FROM information_schema.columns
   WHERE data_type IN ('char','varchar','text','mediumtext','longtext')
     AND character_set_name IS NOT NULL
   GROUP BY 1,2,4,7 HAVING COUNT(DISTINCT collation_name)>1" > 44_charset_mix.txt
$M -e "SELECT * FROM mysql.innodb_table_stats ORDER BY last_update DESC LIMIT 30" > 45_stats.txt

# 5. 索引健康（需 sys schema）
$M -e "SELECT * FROM sys.schema_redundant_indexes LIMIT 50" > 50_redundant_idx.txt
$M -e "SELECT * FROM sys.schema_unused_indexes LIMIT 50"    > 51_unused_idx.txt
$M -e "SELECT * FROM sys.statements_with_full_table_scans
   WHERE db NOT IN ('sys') ORDER BY no_index_used_count DESC LIMIT 30" > 52_full_scan.txt

# 6. 配置漂移
$M -e "SELECT VARIABLE_NAME,VARIABLE_SOURCE,SET_TIME,SET_USER FROM performance_schema.variables_info
   WHERE VARIABLE_SOURCE NOT IN ('COMPILED','NULL')" > 60_var_source.txt

# 7. OS 层（自建实例；云 RDS 跳过并改用监控导出）
(uptime; echo ---; free -g; echo ---; vmstat 1 3; echo ---; iostat -x 1 3; echo ---; \
 df -hT; echo ---; cat /sys/kernel/mm/transparent_hugepage/enabled; echo ---; \
 ulimit -n; echo ---; ls "$($M -sN -e 'SELECT @@datadir' | tail -1)" | head -50) > 70_os.txt 2>/dev/null || true
$M -sN -e "SELECT @@log_error" | tail -1 | xargs -I{} sh -c 'tail -500 {} > 71_error_log_tail.txt' 2>/dev/null || true

# 8. 备份痕迹（自建示例，按实际路径改）
{ ls -lhrt /backup/mysql 2>/dev/null | tail -20; find /backup -name '*xbackup*' -mtime -2 2>/dev/null; } > 80_backup.txt
echo "巡检采集完成：$(pwd)"
```

无 `sys` schema 或权限受限时，用纯 I_S 写法：

```sql
-- 无主键表（可靠写法，兼容 5.7/8.0）
SELECT t.table_schema, t.table_name, ROUND((t.data_length+t.index_length)/1024/1024/1024,2) gb
FROM information_schema.tables t
LEFT JOIN information_schema.statistics s
       ON s.table_schema=t.table_schema AND s.table_name=t.table_name AND s.index_name='PRIMARY'
WHERE t.table_type='BASE TABLE'
  AND t.table_schema NOT IN ('mysql','sys','information_schema','performance_schema')
  AND s.index_name IS NULL
ORDER BY gb DESC;

-- 全表扫描热点（不依赖 sys）
SELECT DIGEST_TEXT, COUNT_STAR, SUM_ROWS_EXAMINED
FROM performance_schema.events_statements_summary_by_digest
WHERE SUM_NO_INDEX_USED > 0 ORDER BY SUM_NO_INDEX_USED DESC LIMIT 30;
```

## 判读检查表（逐项打勾，缺项写"待采集"）

**A 可用性与重启线索**
- [ ] `Uptime` 是否 > 24h；短则必须核对是否发生过重启
- [ ] 错误日志是否有 `Got signal` / `Assertion failure` / `Page check sum` / `not shutdown normally` / OOM
- [ ] 累计计数器是否被重置（说明重启或 `FLUSH STATUS`）

**B 资源**
- [ ] CPU：`us`/`sy`/`wa` 分别占多少，对应哪条决策树（T1/T6/T9）
- [ ] 内存：BP + 连接峰值内存总账是否 < 物理内存 85%；`si/so` 是否长期为 0
- [ ] IO：`%util`、`await` 与云规格上限
- [ ] 磁盘：使用率 + **7/30 天增速** + 触顶日期
- [ ] `lsof +L1` 是否有已删除未释放的大文件

**C 连接与线程**
- [ ] `Threads_connected/max_connections`、`Threads_running` vs 核数
- [ ] 来源 IP / 用户分布是否集中；异常 `Sleep` 数量
- [ ] `Aborted_connects`、`Aborted_clients` 速率
- [ ] `max_used_connections` vs 上限（历史上是否触顶）

**D 锁与事务**
- [ ] `Innodb_row_lock_current_waits`、`Innodb_row_lock_time_avg`
- [ ] 死锁次数与 `LATEST DETECTED DEADLOCK` 内容
- [ ] 最长事务运行时长 / 修改行数（> 60s 或 > 10 万行必须点名）
- [ ] 是否有 PENDING 的 MDL（DDL 撞长事务的前兆）
- [ ] History list length

**E InnoDB 与缓存**
- [ ] BP 命中率、`buffer_pool_wait_free` 增量
- [ ] 脏页比例、刷盘速率与 `innodb_io_capacity` 是否匹配
- [ ] redo 等待（5.7 `Innodb_log_waits`）/ redo 容量是否偏小
- [ ] `Created_tmp_disk_tables` 占比、`Sort_merge_passes` 增量

**F 复制与高可用**
- [ ] IO/SQL 线程双 Yes；`Last_*_Error`
- [ ] 延迟值与推进情况；是否可信（`Seconds_Behind_Source` 局限）
- [ ] 并行 worker 是否启用；`replica_preserve_commit_order`
- [ ] GTID 主从集合是否一致；`gtid_mode`/`enforce_gtid_consistency`
- [ ] 半同步是否降级；`read_only`/`super_read_only` 是否为 ON
- [ ] 从库数量与拓扑；是否存在单点（只有一台从库且承载读）

**G 空间与 Schema 风险**
- [ ] Top 10 大表及其增长；是否有超大单表（> 50GB / > 5 亿行）
- [ ] 碎片率 > 30% 的表
- [ ] binlog 总量与过期策略；undo 表空间大小
- [ ] 无主键表清单（🔴 默认红）
- [ ] 自增余量 > 50% 的整型列
- [ ] 同库内字符集/排序规则混用（连接失效隐患）
- [ ] 冗余索引与长期未使用索引清单
- [ ] `ROW_FORMAT` 是否统一（`Dynamic`）、是否存在 MyISAM 表

**H 配置与安全**
- [ ] 运行时值 vs 配置文件值不一致的参数（"重启后变回去"隐患）
- [ ] 主从关键参数差异（`binlog_format`、`transaction_isolation`、`character_set_*`、`sql_mode`、`innodb_buffer_pool_size`）
- [ ] `sql_mode` 是否含 `STRICT_TRANS_TABLES`
- [ ] 慢日志是否开启、`long_query_time` 是否合理（> 1s 通常偏松）
- [ ] 高危账号：`%` host、长期未使用仍活跃、无 `caching_sha2_password`
- [ ] 网络与 TLS、`skip_name_resolve`
- [ ] 备份：最近一次全备时间、保留策略、**是否做过恢复演练**、binlog 是否覆盖全备起点
- [ ] 监控与告警覆盖度：是否缺磁盘/延迟/锁等待告警

## 多实例场景附加产出

**参数漂移矩阵**：以模板实例为基准，列出各实例差异参数（只列关键参数集，避免噪声）。
**容量横向对比**：同规格实例的实际负载分布，识别"一台过载、三台闲置"。
**结构横向对比**：同名表在不同实例的索引差异（分库分表环境的高频事故源）。
