---
name: mysql-tuning-advisor
version: 1.0.0
description: Review MySQL configuration and resource allocation against the actual workload — memory budget, redo/undo, flush policy, connections, IO settings and 8.0-specific switches — with expected effect, risk and rollback for each change.
name_en: Tuning Advisor
name_zh: 参数调优
description_en: Review configuration and resource allocation against real workload (memory budget, redo, flush policy, connections, IO, 8.0 switches) with effect, risk and rollback.
description_zh: 基于实际负载审查 MySQL 配置与资源分配：内存总账、redo/undo、刷盘策略、连接与线程、IO 与日志、8.0 新特性开关。每条建议给预期效果、风险等级与回退方式。
user-invocable: true
argument-hint: 贴 SHOW GLOBAL VARIABLES + STATUS（两次采样）+ 机器规格与业务负载特征
argument-hint-en: Paste SHOW GLOBAL VARIABLES + two STATUS samples + machine spec and workload profile
argument-hint-zh: 贴 SHOW GLOBAL VARIABLES + STATUS（两次采样）+ 机器规格与业务负载特征
---

# 参数调优

**立场：多数 MySQL 性能问题不该靠调参数解决。** 本技能的第一产出是"这个瓶颈是不是参数导致的"，如果不是，直说并转对应技能（索引 → @SQL 体检；容量 → 架构）。

判读依据：[指标阈值基准](../mysql-ops-knowledge/references/metrics-thresholds.md)
参数细节与默认值判断：[参数审查手册](references/parameter-guide.md)
安全红线：[安全红线与执行分级](../mysql-ops-knowledge/references/safe-execution-rules.md)
输出格式：[调优建议报告模板](references/tuning-report-template.md)

## 开工前必须的输入（缺一即先索要，但一次问全）

| 必需 | 为什么必需 |
|:---|:---|
| 机器规格（CPU 核数 / 内存 / 盘型与 IOPS 上限 / 是否混部） | 所有内存与 IO 参数都以容量为边界 |
| MySQL 版本与形态（自建 / 云 RDS 及规格） | 决定哪些参数可改、是否需重启 |
| `SHOW GLOBAL VARIABLES` + **间隔 60s 的两次** `SHOW GLOBAL STATUS` | 单次 STATUS 是累计值，**算不出速率就无法判读**（这是调优最常见的错误输入） |
| 负载特征：读写比、QPS/TPS、是否有批量写入、延迟敏感度 vs 丢数据容忍度 | 同一参数在 OLTP 与批量场景结论相反 |
| 当前最痛的现象（慢？连接不够？延迟？磁盘满？） | 决定优化目标的优先级与取舍 |

## 调优主流程

### 第 1 步：确立目标（必须写下来）
从这三类里选**一个主目标**，其余明确为不可牺牲项：
- **吞吐优先**（可接受延迟抖动）
- **低延迟优先**（可接受吞吐上限更低）
- **持久性优先**（`sync_binlog=1` + `trx_commit=1`，绝不丢）
目标决定第 4 步刷盘与日志参数的取舍方向。**没有目标的调优都是耍流氓**——尤其涉及持久性权衡时必须让业务确认。

### 第 2 步：核对内存总账（最高频的结构性问题）
```
BP 目标 ≈ 物理内存 × (独占 70–75% | 混部 50–60%)
可分配给会话的余量 = 物理内存 × 85% − BP − 其他进程 − OS 预留
每连接最坏内存 ≈ sort_buffer + join_buffer + read_buffer + read_rnd_buffer + thread_stack (+ tmp_table 上限)
校验：每连接最坏内存 × max_connections < 余量   ← 不满足就是 OOM 定时炸弹
```
常见错法：`sort_buffer_size`/`join_buffer_size` 设成 MB 甚至 GB 级"为了快"（它们是**每连接每操作**分配，直接放大几十倍内存风险，收益边际）。BP 超过物理内存 80%（留下不足页缓存与连接内存）。
具体取值口径见 [参数审查手册 §1](references/parameter-guide.md)。

### 第 3 步：核对 redo / binlog / 刷盘
- redo 容量是否匹配写突发：用 `Innodb_os_log_written` 速率算**checkpoint 年龄**，redo 过小会导致周期性"抖动式"卡顿（比缺索引更难查）。8.0.30+ 用 `innodb_redo_log_capacity`。
- 刷盘双 1（`sync_binlog=1` + `innodb_flush_log_at_trx_commit=1`）是持久性正确基线，**不能为了性能默认建议改成 2/1000**。若要改，必须写清"主机崩溃最多丢多少事务"并要业务确认。
- `innodb_flush_method=O_DIRECT`（避免双重缓存）——需重启，走 @变更评审。
- `innodb_io_capacity(_max)` 必须与**实际盘能力**匹配（SSD 设成 200 是严重低估，机械盘设成 20000 会打爆 IO）。
- `innodb_max_dirty_pages_pct` 与 `_lwm` 决定刷盘平滑度。

### 第 4 步：核对连接与线程模型
- `max_connections`：按第 2 步内存总账反推上限，不要拍脑袋给 5000。
- `thread_cache_size`：用 `Threads_created` 增速判断是否偏小（自动扩缩在多数场景够用）。
- `table_open_cache` / `table_definition_cache`：`Open_tables`、`Opened_table_definitions` 增速判断。
- 高并发短连接场景 → 建议连接池/中间件（ProxySQL、MySQL Router、云代理），**而不是无限提高 `max_connections`**。
- `table_open_cache_instances`、`innodb_buffer_pool_instances` 减少争用（核数多时）。

### 第 5 步：核对临时表、排序、分组
`tmp_table_size` / `max_heap_table_size`（取两者较小值生效）与 `Created_tmp_disk_tables` 占比联动判断。
`sort_buffer_size` 保持小（256K–1M 级起步），**优先用索引消除排序**而不是加大 buffer。
`group_concat_max_len`、`max_allowed_packet`（大包场景常见）单独确认。

### 第 6 步：8.0 / 5.7 特性与陷阱
逐项评估（详见 [参数审查手册 §7](references/parameter-guide.md)）：
- 自增默认缓存、`information_schema` 统计（`innodb_stats_auto_recalc`、`innodb_stats_persistent`）
- `innodb_dedicated_server=ON`（可自动推 BP/redo/flush_method；**启用前必须说明它会覆盖哪些手工值**）
- `binlog_transaction_dependency_tracking`、`replica_parallel_*` 对从库延迟的实质收益
- `caching_sha2_password`、`utf8mb4_0900_ai_ci` 与旧客户端/连接的兼容坑
- 直方图（`ANALYZE TABLE ... UPDATE HISTOGRAM`）作为统计信息失真的补充手段
- `performance_schema` 的开销与必要的 consumer 开关

### 第 7 步：输出建议（每条必须齐 8 要素）
```
参数名 | 当前值 | 建议值 | 依据指标（实测值 + 阈值） | 预期效果（量化区间） | 生效方式（动态/重启） | 风险与副作用 | 回退命令
```
并按 **[改动顺序]** 编排：**一次只改一组相关参数**，给出改后观察时长与判停标准。
"重启才生效"的参数单独列一张表（这些要走 @变更评审 排窗口）。

### 第 8 步：明确"不建议改"的清单
同样重要的一节。逐条写"看起来该调但我们建议保持默认/维持现值，因为……"。
理由包括：无实测依据、风险大于收益、真正瓶颈在别处（指向具体技能）、或属于持久性基线不能牺牲。

## 禁忌

- ❌ 不看负载特征直接套"MySQL 优化模板/my.cnf 模板"。
- ❌ 只凭单次 `SHOW GLOBAL STATUS` 判读增量类指标。
- ❌ 建议把 `sync_binlog` / `innodb_flush_log_at_trx_commit` 降级而不写清丢数据窗口、不要求业务确认。
- ❌ 建议"加大 `sort_buffer_size`/`join_buffer_size` 提速"作为默认动作（内存总账优先）。
- ❌ 一次输出 20 条参数改动。**建议改动项超过 8 条通常意味着你没找到真正的瓶颈。**
- ❌ 用他人环境的值当作依据；所有推荐值必须能追溯到本机实测或明确的容量公式。
- ❌ 忽略"参数没变但性能变差"的场景——那多半不是参数问题。

## If Connectors Available

If **数据库** 已连接：
- 自动采 `variables` + 两次 `status` 快照并算速率，直接完成内存总账校验，无需用户粘贴。

If **监控指标** 已连接：
- 取 7–30 天负载曲线判断"是否需要为峰值容量调参"，避免按瞬时值调参。

If **文档平台** 已连接：
- 调优报告发布为文档，形成参数基线，便于后续漂移比对。

If **变更管理（工单/审批）** 已连接：
- 需重启的参数自动挂到变更单，并生成 @变更评审 的方案骨架。

If 无连接器（默认）：
- 报告落盘 `outputs/tuning-<实例>-<YYYYMMDD>.md`；采集命令以代码块给出。
