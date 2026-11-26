# 指标阈值基准

判定口径：**绿 = 正常**，**黄 = 需关注（纳入巡检问题清单，排期处理）**，**红 = 需处理（立即介入）**。

阈值为通用互联网业务经验值。有业务基线的以基线为准（如"平时 500 QPS，现在 3000"属红，即使绝对值不高）。云 RDS 以规格上限为分母算使用率。

## 1. 可用性

| 指标 | 取值来源 | 绿 | 黄 | 红 |
|:---|:---|:---|:---|:---|
| 实例存活 | `mysqladmin ping` / 云控制台 | 可连 | — | 不可连 / 反复重启 |
| 启动时间 | `SHOW GLOBAL STATUS LIKE 'Uptime'` | > 24h | — | < 10min（刚重启，必须查错误日志） |
| 连接可达率 | 应用侧探活 | 100% | 偶发超时 | 持续报错 |
| Aborted 增长 | `Aborted_connects` / `Aborted_clients` 速率 | < 1/s | 1–10/s | > 10/s（网络/超时/密码/握手包问题） |

## 2. 连接与线程

| 指标 | 取值来源 | 绿 | 黄 | 红 |
|:---|:---|:---|:---|:---|
| 连接使用率 | `Threads_connected / max_connections` | < 60% | 60–80% | > 80%（濒临 `Too many connections`） |
| 活跃线程 | `Threads_running` | < CPU 核数×2 | 核数×2–×4 | > 核数×4（排队/雪崩前兆） |
| 长时间活跃 | `information_schema.processlist` 中 `TIME>5 AND COMMAND='Query'` | 0–2 | 3–10 | > 10 或单条 > 60s |
| 缓存表打开 | `Open_tables / table_open_cache` | < 80% | 80–95% | > 95% |
| 单 IP / 单用户连接数 | `processlist` 聚合 | — | 占比 > 50% | 一个来源打满（连接池泄漏） |

**误区**：`Threads_connected` 高但 `Threads_running` 低 → 是连接池配置过大/未回收，不是数据库慢，止血方向是调池而非杀查询。

## 3. 吞吐与负载

| 指标 | 取值来源 | 判读 |
|:---|:---|:---|
| QPS / TPS | `Questions` / `Com_commit`+`Com_rollback` 增量 | 与基线比，突变 ±50% 即需解释 |
| 读写比 | `Com_select` vs `Com_insert/update/delete` | 决定优化方向（读→索引/缓存；写→事务/刷盘/批量） |
| 慢查询数 | `Slow_queries` 速率 | 红：> 1/s 或较基线增长 10 倍 |
| 扫描比 | `Handler_read_rnd_next / Questions` | 高说明大量全表扫描 |
| 排序 | `Sort_merge_passes` 增长 | 红：持续增长 → `sort_buffer_size` 不足或排序列无索引 |
| 临时表 | `Created_tmp_disk_tables / Created_tmp_tables` | 绿 < 10%，黄 10–25%，红 > 25%（磁盘临时表） |
| 表锁 | `Table_locks_immediate` vs `..._waited` | waited 占比 > 1% 需查 MyISAM / MDL |

## 4. InnoDB 核心

| 指标 | 取值来源 | 绿 | 黄 | 红 |
|:---|:---|:---|:---|:---|
| Buffer Pool 命中率 | `1 - Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests` | > 99.9% | 99–99.9% | < 99%（内存不足或大表扫描污染） |
| 脏页比例 | `Innodb_buffer_pool_pages_dirty / ..._pages_total` | < 25% | 25–60% | > 60% 且逼近 `innodb_max_dirty_pages_pct`（刷盘跟不上） |
| 待刷队列 | `Innodb_buffer_pool_wait_free` | 0 | 偶增 | 持续增长（BP 太小/无空闲页） |
| 预读/同步读 | `Innodb_data_reads` / `Innodb_buffer_pool_read_requests` | 读放大可控 | — | 同步随机读暴增（IO 瓶颈） |
| redo 等待 | `Innodb_log_waits`（5.7）/ `Innodb_redo_log_capacity` 相关（8.0.30+） | 0 | — | > 0（redo 太小，写突发被阻塞） |
| redo 刷盘 | `Innodb_os_log_written` 速率 | 平稳 | 周期性尖峰 | 尖峰且 IO util 高（批量大事务） |
| undo/purge lag | `Innodb_purge_*` / history list length（`SHOW ENGINE INNODB STATUS` 的 `History list length`） | < 10 万 | 10–100 万 | > 100 万（长事务/回滚段膨胀） |
| 行锁等待 | `Innodb_row_lock_time_avg` / `Innodb_row_lock_waits` 速率 | avg < 50ms | 50–500ms | > 500ms 或 `Innodb_row_lock_current_waits` 持续 > 0 |
| 死锁 | `Innodb_deadlocks` / 错误日志 | 0–偶发 | 持续出现 | 高频且影响业务（需查具体事务） |

## 5. 复制与高可用

| 指标 | 取值来源 | 绿 | 黄 | 红 |
|:---|:---|:---|:---|:---|
| 复制线程 | `SHOW REPLICA STATUS` 的 `Replica_IO_Running` / `Replica_SQL_Running` | 均 Yes | 均 Yes 但有重试 | 任一 No（看 `Last_*_Error`） |
| 延迟秒数 | `Seconds_Behind_Source` | < 5s | 5–60s | > 60s，或长期为 `NULL`（线程挂了/断链） |
| 真实延迟 | 心跳表 / `pt-heartbeat` | < 5s | — | > 30s（`Seconds_Behind_Source` 在单线程 SQL 下不可全信） |
| 并行复制 | `Replica_parallel_workers` vs `Last_SQL_Errno` | worker>0 | =0（5.6 及以前单线程） | 大事务串行回放导致积压 |
| GTID 一致性 | `GTID_MODE=ON`、`Executed_Gtid_Set` 主从比对 | 一致 | 差异可解释 | 主从数据集不一致（需校验修复） |
| 半同步 | `Rpl_semi_sync_*_status` | 符合预期 | 降级为异步 | 意外降级（网络/从库故障） |
| 只读保护 | `read_only` / `super_read_only` | 从库 ON | — | 从库 OFF（有双写风险） |

## 6. 空间与 IO

| 指标 | 取值来源 | 绿 | 黄 | 红 |
|:---|:---|:---|:---|:---|
| 数据盘使用率 | `df` / 云监控 | < 70% | 70–85% | > 85%（云 RDS 会被锁定，通常 ~90%） |
| 增长趋势 | 巡检历史 / `data_free` | 可预测 | 7 天内破 85% | 3 天内破 90% |
| binlog 占用 | `SHOW BINARY LOGS` + `binlog_space_limit` | 可控 | 无过期策略 | 单目录占满磁盘 |
| IO util / await | `iostat -x` / 云监控 IOPS | util<60% | 60–90% | >90% 或 await 显著抬升（读延迟） |
| 大表 | `information_schema.tables` 排序 | — | 单表 > 50GB 或 > 5 亿行 | 继续暴涨且无归档方案（DDL 成本极高） |
| 碎片率 | `DATA_FREE / (DATA_LENGTH+INDEX_LENGTH)` | < 10% | 10–30% | > 30%（需评估 OPTIMIZE/重建） |
| 自增余量 | 自增列类型 vs 当前值 | 剩余 > 50% | 20–50% | < 20%（`INT` 溢出会直接导致写入失败） |

## 7. 内存与 OS

| 指标 | 判据 |
|:---|:---|
| 物理内存 | `BP + 所有连接峰值内存（join/sort/read-buffer × max_connections） + 其他进程 < 物理内存 × 85%`。超了 → OOM 风险 |
| Swap | `vmstat` 的 `si/so` 长期 > 0 即红（数据库进程被换出，延迟剧烈抖动） |
| `vm.swappiness` | 建议 ≤ 1；为 60 且内存吃紧 → 需改 |
| THP | `cat /sys/kernel/mm/transparent_hugepage/enabled` 非 `[never]` → 黄（可能造成分配卡顿） |
| 文件描述符 | `Open_files / ulimit -n` > 80% → 红 |
| CPU | 用户态高 → 找 SQL；系统态高 → 找上下文切换/中断/大量连接抖动；`iowait` 高 → IO |
| NUMA | 多 NUMA 节点且 BP 巨大、跨节点访问高 → 评估 `innodb_numa_interleave` |

## 8. 安全与配置健康

| 项 | 红 |
|:---|:---|
| 账号 | 存在 `%` 通配 host 的高权限账号；`root@%` 可远程；无人使用的账号仍活跃 |
| 认证 | 8.0 仍有账号使用 `mysql_native_password` 且业务已支持 `caching_sha2_password` |
| TLS | 未启用加密传输，或证书过期 |
| `sql_mode` | 为空/不含 `STRICT_TRANS_TABLES` → 静默截断脏数据（红） |
| 审计 | 核心库无审计日志、无慢日志、`log_queries_not_using_indexes` 与实际需求不匹配 |
| 参数漂移 | 主从关键参数（`binlog_format`、`transaction_isolation`、`character_set_*`）不一致 |
