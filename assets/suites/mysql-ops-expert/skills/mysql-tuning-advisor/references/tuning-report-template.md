# 调优建议报告模板

文件名：`outputs/tuning-<实例>-<YYYYMMDD>.md`

---

# 参数与资源审查：<实例>

| 项 | 值 |
|:---|:---|
| 版本 / 形态 | MySQL `8.0.36` / 自建 `16C64G` NVMe（云 RDS `<规格>`） |
| 数据量 / 热数据 | `X` GB / 估算热数据 `Y` GB（依据 BP 命中率与 `Innodb_buffer_pool_reads` 速率） |
| 负载特征 | QPS `<n>`、TPS `<n>`、读写比 `<a:b>`、峰值时段 `<...>`、批量写入 `<有/无>` |
| 数据来源 | `SHOW GLOBAL VARIABLES` + `GLOBAL STATUS` 两次采样（`10:00:00` 与 `10:01:00`）+ `SHOW ENGINE INNODB STATUS` + `<监控导出>` |
| **调优主目标** | `<低延迟优先 / 吞吐优先 / 持久性优先>`；不可牺牲项：`<...>` |

## 一、内存总账校验（一票否决项）

| 项 | 值 |
|:---|:---|
| 物理内存 | 64 GB |
| `innodb_buffer_pool_size` | 48 GB（75%） |
| 每连接最坏内存 | `sort 1M + join 1M + read 128K + rnd 1M + stack 512K + tmp 上限` ≈ **4.2 MB** |
| `max_connections` × 每连接 | 800 × 4.2 MB ≈ **3.3 GB** |
| P_S + 其他进程 + OS 预留 | `2 GB + 4 GB + 4 GB` |
| **合计 vs 85% 上限** | 61.3 GB vs 54.4 GB → ❌ **超账，OOM 风险** |

**结论**：`<内存总账不成立，需先解决容量问题>`；具体见建议 A-01/A-02。
（**这一节不通过时，后续参数建议一律标注"依赖本节先落地"**。）

## 二、实测指标与阈值对照

| 指标 | 实测 | 阈值基准 | 判定 | 含义 |
|:---|:---|:---|:---|:---|
| BP 命中率 | 99.97% | > 99.9% 绿 | 🟢 | BP 不小，无需扩 |
| `Created_tmp_disk_tables` 占比 | 34% | > 25% 红 | 🔴 | 落盘临时表（进一步看是否含 `TEXT` 列，若是则调参无效） |
| `Innodb_log_waits` | 5.2/s | > 0 红 | 🔴 | redo 偏小，与写突发不匹配 |
| 脏页比例 | 61% | > 60% 红 | 🔴 | 刷盘跟不上（`innodb_io_capacity=200` vs NVMe 实测 5 万 IOPS） |
| `Sort_merge_passes` | 0.3/s | 持续增长红 | 🟡 | 排序 buffer 偏小 **或** 应改用索引消除排序 |
| `Threads_created` | 45/s | — | 🟡 | 线程缓存不足（连接抖动） |
| 复制延迟 | 22 s | < 5 s | 🟡 | `replica_parallel_workers=0` |

## 三、建议改动（按执行顺序）

### 组 1：可动态生效、风险低（今天可做）
| # | 参数 | 当前 | 建议 | 依据指标 | 预期效果 | 风险 | 回退 | 级别 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| A-01 | `innodb_io_capacity` | 200 | 8000 | 脏页 61% + NVMe 实测 50k IOPS | 脏页比例 < 30%，消除刷盘抖动 | 刷盘抢业务 IO | `SET GLOBAL innodb_io_capacity=200;` | L1 |
| A-02 | `innodb_io_capacity_max` | 400 | 16000 | 同上 | 追赶能力 | 同上 | 回退 400 | L1 |
| A-03 | `thread_cache_size` | 自动 | 256 | `Threads_created` 45/s | 降至 < 1/s | 内存可忽略 | 回退 | L1 |
| A-04 | `replica_parallel_workers`(从库) | 0 | 8 | 延迟 22s | 延迟 < 5s | 需 `STOP REPLICA` 重启线程 | 回退 0 | L1 |

```sql
-- 执行（先在从库验证 30 min，再主库）
SET GLOBAL innodb_io_capacity = 8000;      -- 记录原值 200
SET GLOBAL innodb_io_capacity_max = 16000;
-- 持久化（防重启回退）：SET PERSIST innodb_io_capacity = 8000;  或同步写入配置文件
```
**观察**：改后 30 min 看 `%util`、`await`、脏页比例、业务 p99。判停：`%util > 85%` 或 p99 上升 > 20% → 回退。

### 组 2：需重启 / 结构性（走 @变更评审）
| # | 参数 | 当前 | 建议 | 依据 | 预期 | 为什么需重启 | 风险 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| B-01 | `innodb_redo_log_capacity` | 256 MB | 4 GB | `Innodb_log_waits` 5/s + redo 写速率 12 MB/s（年龄 ≈ 21s） | 消除周期性卡顿 | 5.7 需改文件大小；8.0.30+ 可在线 resize（**优先走在线**） | 崩溃恢复时间变长（约 `<min>`） |
| B-02 | `innodb_flush_method` | `fsync` | `O_DIRECT` | 内存总账吃紧 + 双缓存 | 回收 page cache 压力 | 静态参数 | 需重启窗口 |

## 四、明确不建议改的

| 参数 | 常见建议值 | 为什么这里不改 |
|:---|:---|:---|
| `innodb_flush_log_at_trx_commit` | "改成 2 提性能" | 当前瓶颈是刷盘能力配置错误（A-01），改持久性策略属**未确认的牺牲**，且业务要求不丢单 |
| `sync_binlog` | "改成 100" | 同上；双 1 是崩溃安全基线 |
| `sort_buffer_size` | "升到 8M" | 每连接分配，内存总账已超（§1）；`Sort_merge_passes` 应通过索引消除排序解决 → 转 @SQL 体检 |
| `max_connections` | "升到 5000" | 内存总账不允许；连接问题根因是慢 SQL 占连接 → 转 @故障应急 R1 |
| `tmp_table_size` | "升到 1G" | 该 digest 含 `TEXT` 列，内存临时表根本不生效 → 需改 SQL |
| `query_cache_*` | — | 8.0 已移除 |

## 五、参数基线（用于后续漂移比对）

```ini
# 建议固化到配置管理的基线（含版本号与生效日期）
[mysqld]
innodb_buffer_pool_size = 48G
innodb_io_capacity      = 8000   # 2026-10-27 变更，依据：NVMe 50k IOPS
sync_binlog             = 1
innodb_flush_log_at_trx_commit = 1
sql_mode                = STRICT_TRANS_TABLES,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO
```

> 本报告基于 `<数据来源与时间窗口>`；未验证项：`<列表>`。所有 L2 以上操作需人工复核并走 @变更评审。
> **调优不等于变更**：本报告仅提出建议，执行前需业务确认目标取舍（尤其 §四 中被拒绝的持久性类改动）。
