# 参数审查手册

口径说明：以下"建议值"均为**从实测反推的方法**，不是可以直接抄的配置模板。所有推荐必须给出本机依据。

## §1 内存与 Buffer Pool

| 参数 | 方法与判据 |
|:---|:---|
| `innodb_buffer_pool_size` | 独占机器：物理内存 50–75%（数据量 < 内存时取"全量热数据 + 30% 余量"）；混部：30–50%。判据：`Innodb_buffer_pool_reads / read_requests`（命中率 < 99% 且有 IO 瓶颈 → 偏小；命中率 > 99.99% 且内存吃紧 → 偏大，可回收） |
| `innodb_buffer_pool_instances` | BP ≥ 1GB 才分实例；`max(1, BP_GB)` 量级，核数少时不要过度拆（每实例有独立 LRU/flush 系统，过多会加重不均衡） |
| `innodb_buffer_pool_chunk_size` | 需支持在线改 BP 时保证 `BP % chunk == 0`，否则在线调整无效 |
| `innodb_dedicated_server` | `ON` 时自动推 `BP`、`redo 容量`、`flush_method`。**副作用：手工设的这三项可能被忽略**（8.0 中显式设置的值仍优先，但不同小版本行为有差异，启用前必须在测试环境确认最终生效值 `SELECT ... FROM performance_schema.variables_info`） |
| 会话 buffer | `sort_buffer_size` 256K–1M、`join_buffer_size` 256K–1M、`read_buffer_size` 128K–256K、`read_rnd_buffer_size` 256K–1M。**这些是每次操作、每连接分配**。仅在确认单查询确实因 buffer 过小产生多次 merge pass 时，在**会话级**临时加大，不改全局 |
| `thread_stack` | 默认 256K–512K；递归深/存储过程复杂时才上调 |
| `max_allowed_packet` | 大 BLOB/长 SQL/大批量 `INSERT` 场景需 ≥ 单条最大包（默认 4–64M 常不够），同时注意客户端侧也有该值 |
| `tmp_table_size` / `max_heap_table_size` | 生效值取两者较小。判据：`Created_tmp_disk_tables / Created_tmp_tables` > 25% 且内存有余 → 适度上调；但要同时检查是否有 `BLOB`/`TEXT` 列导致**内存临时表根本无法使用**（8.0 前含大字段列的临时表必落盘）——此时调参无效，需改 SQL |

**内存总账公式（必须写进报告）**
```
物理内存 × 0.85 ≥ BP
  + (sort+join+read+rnd+thread_stack) × max_connections   ← 最坏情况假设
  + performance_schema 上限 + OS page cache 预留 + 同机其他进程
```
不满足时的处置顺序：**降会话 buffer 默认值 → 降 `max_connections` 并改用连接池/中间件 → 加内存**，而不是"减小 BP 挪给会话"。

## §2 日志与持久性

| 参数 | 判据与代价 |
|:---|:---|
| `innodb_redo_log_capacity`（8.0.30+）/ `innodb_log_file_size × innodb_log_files_in_group` | 用 `Innodb_os_log_written` 速率算：目标 redo 容量 ≈ **checkpoint 年龄不超过 1 小时的写入量**（写突发大时取 1.5–2h）。判据：5.7 的 `Innodb_log_waits > 0` 说明 redo 太小；8.0.30+ 看 `Innodb_redo_log_oldest_checkpoint_lsn` 与当前 LSN 差值。**过小 → 周期性剧烈刷脏抖动；过大 → 崩溃恢复时间变长** |
| `innodb_flush_log_at_trx_commit` | `1` = 每次提交刷盘（ACID 正确基线）；`2` = 每秒刷，**OS/主机崩溃丢最多 ~1s 事务**；`0` = 每秒写+刷，mysqld 崩溃也可能丢。改动前必须量化"丢 1s ≈ 多少 TPS × 1s 的订单"并让业务签字 |
| `sync_binlog` | `1` 为基线；`100–1000` 提升吞吐但崩溃丢对应事务。注意与 `trx_commit` 的组合：**双 1 才是"配置了 binlog 的崩溃安全线"** |
| `binlog_expire_logs_seconds` / `expire_logs_days` | 必须 ≥ 全备周期 + 余量，否则**PITR 链断裂**。下游有 DTS/Canal 时以消费最慢任务位点为准 |
| `innodb_flush_method` | Linux SSD/云盘推荐 `O_DIRECT`（避免双重缓存与额外内存压力）；**需重启** |
| `innodb_io_capacity` / `_max` | 与**实测盘 IOPS** 对齐：SSD/NVMe 常用 2000–20000；机械盘 100–200。`_max` 用于突发追赶（一般 2×）。设太高 → 刷盘抢占业务 IO（表现为周期性延迟尖峰）；设太低 → 脏页堆积、checkpoint 停滞、最后被迫剧烈刷脏 |
| `innodb_max_dirty_pages_pct` / `_lwm` | 默认 90/10。脏页长期高位 + IO 有余 → 可下调 lwm 提前平滑刷盘 |
| `innodb_purge_threads` | History list length 持续高（> 100 万）且有长事务 → 先治长事务，再考虑加 purge 线程 |
| `innodb_log_buffer_size` | 大事务（一次改几十万行）会撑大 log buffer；`Innodb_log_waits` 增长时上调 |
| `innodb_doublewrite` | 保持 `ON`（关闭 = 页撕裂风险，属 L3）；只有"自身有可靠写时复制/原子写存储"的极端场景才评估 |
| `innodb_checksum_algorithm` / `innodb_strict_mode` | 保持默认开启 |

## §3 连接与并发

| 参数 | 判据 |
|:---|:---|
| `max_connections` | 由内存总账反推；`max_used_connections` 曾逼近上限 → 评估上调并留 20% 余量。**不要为了消除报错而无脑调大** |
| `admin_address` + `additional_mem_allowed`(视版本) / `extra_port` | 生产实例应配管理通道，避免连接打满后进不去（这是应急能力，不是性能参数） |
| `thread_cache_size` | `-1`（自动）通常足够；`Threads_created` 增速高（> 数十/s）→ 手工上调（如 128–256） |
| `wait_timeout` / `interactive_timeout` | 必须与应用连接池 `idleTimeout`/`minEvictableIdleTime` 协调：**服务端超时 > 池回收时间**，否则应用拿到已失效连接（表现为 `Communications link failure`） |
| `net_read_timeout` / `net_write_timeout` | 大结果集/慢客户端导出时 `net_write_timeout` 偏小会造成 `Broken pipe` |
| `table_open_cache` / `_instances` / `table_definition_cache` | `Open_tables` 接近上限、`Opened_tables`/`Opened_table_definitions` 持续增长 → 上调。经验：`table_definition_cache ≈ 表数量 × 2`（多库多表环境） |
| `lock_wait_timeout`（MDL）vs `innodb_lock_wait_timeout`（行锁） | 两者名字像但完全不同层面。DDL 会话应设小 `lock_wait_timeout`（拿不到 MDL 快速失败，不阻塞他人） |
| 线程池（Percona/企业版 `thread_pool_*`） | 高并发短连接 + 大量上下文切换（`sy` 高）时可显著改善；开启需完整压测，属结构性变更 |

## §4 复制相关（影响性能）

| 参数 | 判据 |
|:---|:---|
| `binlog_format=ROW` | 现代默认与恢复/闪回能力的前提 |
| `binlog_row_image=FULL` | 误删找回能力的前提（`MINIMAL` 省 binlog 但让闪回不可用 —— 明确取舍） |
| `replica_parallel_type` / `replica_parallel_workers`（5.7: `slave_parallel_*`） | 从库延迟的主要治理手段。`LOGICAL_CLOCK` + worker = 8–16 常见起点；8.0.26+ 用 `replica_parallel_workers` + `replica_preserve_commit_order=ON`；`binlog_transaction_dependency_tracking=WRITESET` 可显著提升并行度（主库侧参数，需评估） |
| `sync_relay_log` / `relay_log_recovery=ON` | 从库崩溃后自动丢弃可能损坏的中继日志并重取，避免"从库起不来/位点错乱" |
| `source_verify_checksums` / `binlog_checksum` | 保持校验开启 |
| `rpl_semi_sync_*` | 追求 RPO≈0 时的手段，代价是写延迟增加（网络 RTT 级） |
| `report_host` / `report_port` | 多从库可识别，运维性参数 |
| `super_read_only` | 从库强烈建议 ON（比 `read_only` 更严格，防误写） |
| `gtid_mode` + `enforce_gtid_consistency` | `ON` 让切换、PITR、多源复制显著更简单可靠。从 `OFF` 迁移需按流程（`OFF→OFF_PERMISSIVE→ON_PERMISSIVE→ON`，`enforce` 先行），**属变更评审范围** |

## §5 字符集、时区与模式（一致性 > 性能）

- `character_set_server=utf8mb4`、`collation_server=utf8mb4_0900_ai_ci`（8.0）/ `utf8mb4_unicode_ci`（5.7）。**同一实例内混用不同 collation 会造成连接列索引失效**（索引手册 I-02）。
- `default_authentication_plugin`：8.0 迁移期客户端兼容问题高发，改动前确认驱动版本。
- `sql_mode` 必须含 `STRICT_TRANS_TABLES`（+`NO_ZERO_DATE`、`ERROR_FOR_DIVISION_BY_ZERO`）。为空意味着静默截断与脏数据，**属数据质量红线**。
- `time_zone` / `system_time_zone`：主从不一致会让基于时间的备份恢复与业务对账全面失真。跨时区部署必须显式。
- `lower_case_table_names`：**初始化后不可改**（改会导致表无法访问），任何变更请求都应拒绝。
- `innodb_force_recovery`：正常运行必须为 0；非 0 期间实例只读且有损坏风险。

## §6 慢日志与可观测（最常被关掉的保命参数）

| 参数 | 建议 |
|:---|:---|
| `slow_query_log=ON` | 必须开 |
| `long_query_time` | 生产常用 0.5–1s（> 1s 通常太松，发现不了劣化）；核心链路可 0.1s |
| `log_queries_not_using_indexes` | 单独开会产生海量噪声（小表全扫也记录）。建议配合 `min_examined_row_limit`（如 1000）使用 |
| `log_slow_extra`（8.0.14+）/ `log_slow_admin_statements` | 建议开启，能拿到更多维度与 DDL 耗时 |
| `performance_schema=ON` | 内存 ≥ 4–8G 的实例保持开启；小内存实例评估 `performance_schema_consumer_*` 按需关闭部分 |
| `innodb_monitor_enable` / 信息统计 | 需要专项诊断时临时开启，用完关闭 |

## §7 5.7 → 8.0 的行为差异（避免"升完变慢/变快"误判）

- 优化器：直方图、`hash join`（8.0.18+）、降序索引、函数索引、`EXPLAIN ANALYZE`、成本模型变化 → **升级后执行计划普遍会变**，升级方案必须包含 Top SQL 计划比对（转 @变更评审）。
- `query_cache` 在 8.0 移除：从 5.7 迁移若依赖查询缓存会出现性能下降（不是 bug，需改用应用/中间件缓存）。
- 数据字典变为事务型 InnoDB：`information_schema` 查询行为与权限模型有差异。
- `innodb_undo_tablespaces`、临时表空间（`ibtmp1`）行为变化；自动扩展临时表空间可收缩。
- 自增列在 8.0 持久化到表空间（5.7 重启后自增值可能"回退"，依赖 `AUTO_INCREMENT` 连续性的逻辑要复查）。
- 默认认证插件、默认 collation（`utf8mb4_0900_ai_ci`）与旧数据比较行为差异。
- `SHOW SLAVE STATUS` → `SHOW REPLICA STATUS`（8.0.22+），`master`/`slave` 术语全面替换。

## §8 什么不该在这里改

| 现象 | 真实方向 |
|:---|:---|
| 单条 SQL 慢 | @SQL 体检（索引/写法），调 buffer 无效 |
| 偶发抖动、周期性尖峰 | 先查长事务、大表 DDL、备份任务、刷脏与 redo 年龄（多为**任务调度**问题） |
| 连接报错 `Too many connections` | 连接池配置 + 慢 SQL 占用 → R2/R1 |
| 从库延迟 | 并行度 + 大事务治理，不是"从库参数随便调" |
| 磁盘不足 | 归档与 binlog 策略 → R8/@备份恢复 |
| 数据倾斜/热点行 | 架构层（拆分、缓冲、合并更新），参数无解，明确说出来 |
