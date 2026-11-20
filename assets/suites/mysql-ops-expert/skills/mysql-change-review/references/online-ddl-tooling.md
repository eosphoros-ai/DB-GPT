# 在线 DDL 工具选型

## 决策流程（按顺序走）

```
变更类型是什么？
├─ 8.0 且属于 INSTANT 白名单？ ────────────→ 原生 INSTANT（秒级，但见下方陷阱）
├─ 原生 INPLACE + LOCK=NONE 支持？
│   ├─ 预计耗时 < 30min 且 表 < 1000 万行 ─→ 原生 INPLACE（仍需 MDL 防护 + 从库延迟评估）
│   └─ 否则 ─────────────────────────────→ gh-ost / pt-osc
├─ 只能 COPY（改主键、部分类型/字符集、5.7 部分场景）─→ gh-ost / pt-osc（禁止主库直接 COPY 大表）
└─ 删表/删列/不可逆 ─────────────────────→ 走两阶段方案（见文末）
```

## 三种原生 ALGORITHM 对比

| | `INSTANT` | `INPLACE` | `COPY` |
|:---|:---|:---|:---|
| 版本 | 8.0.12+ | 5.6+ | 全部 |
| 重建数据 | 否（仅改元数据） | 否（多数）/ 是（部分） | 是（全表重写） |
| 阻塞 DML | 否 | 否（`LOCK=NONE` 时） | 是（锁读+写） |
| 耗时 | 秒级 | 与行数弱相关（加索引与数据量正相关） | 与数据量强正相关 |
| 空间峰值 | 几乎无 | 中等（临时排序/日志） | 约 2× 表大小 |
| MDL 风险 | **有**（开始/结束瞬间拿写锁） | **有** | **有** |
| 从库延迟 | 极低 | 与主库执行时间同量级 | ≈ 主库执行耗时 |
| 支持回滚 | 元数据级 | 中途失败需清理 `#sql-*` | 中途失败需清理 |

### INSTANT 的陷阱（必须写进方案）
- 加列后行的"版本"信息累积（`row_versions`），多次 INSTANT 加列后，**下一次非 INSTANT 的 DDL 会变慢**（需重建多版本行）。
- 加**主键**不能用 INSTANT；`ROW_FORMAT=COMPACT` 不支持；改列类型基本不支持。
- INSTANT 加列后，`SELECT *` 的应用在读旧行时用默认值填充——若新列 `NOT NULL` 有默认值需确认应用逻辑一致。
- **INSTANT 后不能直接 `DROP COLUMN` 回到旧结构**（8.0 的 DROP COLUMN 也是 INSTANT，但会留下"不可用列"占位，需 `ALGORITHM=COPY` 或表重建才真正回收）。

### INPLACE 期间必须做的 MDL 防护
```sql
-- 会话级：拿不到锁快速失败，不阻塞后来者  [L1，仅本会话]
SET SESSION lock_wait_timeout = 10;
SET SESSION transaction_isolation = 'READ-COMMITTED';  -- 视场景，减少锁范围
ALTER TABLE <tbl> ADD INDEX idx_x (x), ALGORITHM=INPLACE, LOCK=NONE;
```
前置检查（执行前 + 卡点判停标准）：
```sql
-- 有无长事务/长查询在目标表上  → 有则先处理，否则 ALTER 会卡在 "Waiting for table metadata lock"
SELECT * FROM information_schema.innodb_trx
 WHERE trx_started < NOW() - INTERVAL 30 SECOND;
SELECT id,time,state,LEFT(info,80) FROM information_schema.processlist
 WHERE info LIKE '%<tbl>%' OR state LIKE '%metadata lock%';
-- 复制是否健康（延迟大会让 DDL 传播更痛）
SHOW REPLICA STATUS\G
```

## gh-ost vs pt-online-schema-change

| 维度 | **gh-ost** | **pt-osc** |
|:---|:---|:---|
| 原理 | 伪装成从库拉 binlog（ROW 格式必需）+ 影子表拷贝 | 触发器同步 + 分块 `INSERT ... SELECT` |
| 前置条件 | `binlog_format=ROW`、`binlog_row_image=FULL`、需 binlog 权限、**不能是级联从库复制目标（需 `--allow-on-master` 或建专用副本）** | 需 `TRIGGER` 权限、表**必须有主键/唯一非空索引** |
| 对表结构约束 | 不支持外键；触发器存在时 `--approve-on-master` 需谨慎 | 与业务自带触发器冲突（会拒绝，需 `--force`，风险自负） |
| MDL 冲击 | 切表瞬间拿一次锁，整体更平滑 | 切表 + 触发器创建/删除多次拿锁 |
| 可观测/可控 | `--max-lag-millis` 自动限速、交互终端可暂停/调速、进度清晰 | `--max-lag`、`--recursion-method`、进度 `--progress` |
| 额外空间 | 一份全表 + binlog 放大 | 一份全表 + binlog 放大 |
| 失败清理 | 自动清理影子表/触发器无（无触发器） | 需 `--no-drop-old-table` 策略与手工清理 |
| 适用默认建议 | **首选**：大表（> 100 GB）、写多、要求平滑 | 次选：环境无 binlog 权限 / 有外键 / 已有触发器场景 |

两者共同代价：**binlog 产出激增**（整表数据以行事件形式重放）→ 下游 DTS/Canal 位点滞后、磁盘压力、从库延迟。必须预留 `表大小 × 1.2~2` 的 binlog 空间并提前通知下游。

常用命令骨架（评审时给出可直接改用的完整命令）：
```bash
gh-ost --host=<h> --port=3306 --user=<ghost_u> --password=*** \
  --database=<db> --table=<tbl> \
  --alter="ADD INDEX idx_x (x)" \
  --chunk-size=1000 --max-lag-millis=1500 --throttle-flag=ghost.<tbl>.throttle \
  --critical-load=Threads_running=80 \
  --initially-drop-old-table=false --approve-power-off=false \
  --switch-stage=nomax --exact-rowcount=false --verbose 2>&1 | tee ghost_<tbl>.log
# 先在从库用 --test-on-replica 演练；正式执行时先不加 --execute（默认干跑，只打印计划），确认无误再追加 --execute
```
```bash
pt-online-schema-change --host=<h> --user=<u> --ask-pass \
  D=<db>,t=<tbl> --alter="ADD INDEX idx_x (x)" \
  --max-lag=1.5 --critical-load=Threads_running=80 --chunk-size=1000 \
  --chunk-time=0.5 --recursion-method=processlist \
  --no-drop-old-table --preserve-triggers \
  --set-vars="lock_wait_timeout=5,transaction_isolation='READ-COMMITTED'" \
  --progress=time,30 --dry-run     # 验证通过后改 --execute
```

## 耗时估算口径（必须给出代入过程）

```
原生 INPLACE 加索引 ≈ 行数 × 每行索引构建成本（经验：1000 万行 / 3 列 int ≈ 3–8 min，SSD）
COPY / gh-ost / pt-osc ≈ 需搬运字节数 ÷ 有效吞吐（保守取 60–120 MB/s；云盘取下限）
   例：200 GB 表 → 200×1024 ÷ 80 ≈ 2560 s ≈ 43 min（未计限速与业务高峰降速，实际按 1.5–2 倍留量）
从库额外延迟 ≈ 主库执行耗时（DDL 事件回放；gh-ost 场景则是行事件回放，量级同表大小）
```
判停标准（写进方案）：`Seconds_Behind_Source > 60` 或 `Threads_running > 核数×3` 或业务错误率 > 基线 0.5% → 立即暂停（gh-ost 用 throttle 文件 / `--max-lag`；原生用 `KILL` 该 DDL 会话并说明回滚开销）。

## 中途变慢/需要中止怎么办（最常被忽略）

| 情况 | 处置 | 说明 |
|:---|:---|:---|
| 原生 DDL 跑很久且业务受影响 | [L2] `KILL <ddl_id>;` | InnoDB 会回滚 DDL，遗留 `#sql-*` 临时文件通常自动清理；**清理前不要手工删文件** |
| gh-ost 太慢 | 调 `--chunk-size` 与 `--max-lag-millis`；或 `--progress` 定位阶段 | 影子表可整表丢弃，中止安全 |
| pt-osc 想中止 | Ctrl-C（其会清理触发器/影子表，除非 `--no-drop-old-table`） | 若遗留，按 `--preserve-triggers` 与实际状态手工核对后再清理 |
| 磁盘不够了 | 立即停止变更（**不要继续，会写满导致实例不可用**） | 回滚 → 清理 binlog → 扩容 → 重来 |

## 两阶段（不可逆变更的标准做法）

用于：删列、改名、改类型（收窄）、加非空约束、字符集统一。
1. **阶段一（本次上线）**：加新列（可空）+ 双写（新旧列同写）或触发任务回填 → 校验一致性 → 应用切读 → 观察 1–2 个业务周期。
2. **阶段二（下次变更）**：停写旧列 → 保留旧列至少一个发布周期 → 确认无回退需求 → 才执行 `DROP COLUMN`。
每个阶段独立可回滚，阶段二必须引用阶段一的校验结果作为准入条件。

## 云上环境补充

- 云 RDS 通常内置"无锁变更 / DDL 优化"功能（如阿里云 DMS 无锁结构变更），**优先用平台能力**，但要确认：是否要求表有主键、是否占用额外空间、变更期间的实例负载归属（多数仍在原实例）。
- 部分参数不可改（`innodb_flush_method`、`innodb_buffer_pool_instances`），方案里不要写不可执行的步骤。
- 大表 DDL 前先确认工单/审批链路与平台限制（有些云对 > 100 GB 的 ALTER 要求提前报备）。
