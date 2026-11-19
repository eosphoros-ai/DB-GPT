---
name: mysql-backup-restore
version: 1.0.0
description: Evaluate backup strategy and design recovery plans — RPO/RTO check, full + binlog chains, point-in-time recovery, accidental-delete rollback via binlog or shadow-table restore, and recovery-drill verification.
name_en: Backup & Recovery
name_zh: 备份恢复
description_en: Assess backup strategy (RPO/RTO, chain completeness, drill evidence) and produce recovery plans: PITR, binlog-based accidental-delete rollback, single-table restore, drills.
description_zh: 评估备份策略（RPO/RTO、备份链完整性、演练证据）并给出恢复方案：按时间点恢复 PITR、误删数据基于 binlog/影子表回滚、单表恢复、恢复演练设计。
user-invocable: true
argument-hint: 说清场景（评估备份策略 / 误删数据 / 整库恢复到新实例）+ 备份方式与时间
argument-hint-en: State the scenario (assess backups / accidental delete / restore to new instance) + backup method and times
argument-hint-zh: 说清场景（评估备份策略 / 误删数据 / 整库恢复到新实例）+ 备份方式与时间
---

# 备份恢复

**第一原则：没做过的恢复不算有备份。** 评估备份的终点不是"有没有备份文件"，而是"能否在要求时间内恢复到要求时间点，并且验证过"。

红线与分级：[安全红线与执行分级](../mysql-ops-knowledge/references/safe-execution-rules.md)
命令：[只读诊断命令清单 §7](../mysql-ops-knowledge/references/command-cheatsheet.md)
策略清单：[备份策略评估清单](references/backup-strategy-checklist.md)
恢复操作：[PITR 与误删找回手册](references/pitr-runbook.md)

## 先分场景（三选一再往下）

| 用户说什么 | 走哪条 | 首要问题 |
|:---|:---|:---|
| "看看我们备份靠不靠谱" / 巡检里备份项存疑 | **路径 A：策略评估** | RPO/RTO 是多少？有没有演练记录？ |
| "误删了数据/更新了没 where" | **路径 B：误删找回**（最高危、最紧急） | 删了什么、什么时候、有没有 binlog、能否停写 |
| "要把库恢复到昨天/新实例" | **路径 C：整库/时间点恢复** | 目标时间点、磁盘够不够、有没有隔离环境 |
| "只要恢复一张表" | **路径 D：单表恢复** | 是否独立表空间、有无外键依赖 |
| 出事后想先确认能不能救 | 先做 **路径 A 的 3 项快查**，再决定 B/C/D | — |

## 路径 B：误删找回（重点，先停手再动手）

**第 0 步：三个必须立刻确认的事**（决定后面所有路径）
1. **立即停止相关写入**（能停就停；不能停也要记录"停止时刻"，因为 binlog 位点越往后越难处理）。
2. **确认 binlog 是否覆盖删除时刻**：`SHOW BINARY LOGS;` + 删除时间点前后的文件是否存在、`binlog_expire_logs_seconds` 是否已清掉、下游是否已消费。
3. **确认是否还在同一事务里**（若误删语句仍在未提交事务中 → **不要提交，直接 `ROLLBACK`**，这是成本最低的解法。先查 `information_schema.innodb_trx`）。

**第 1 步：定影响面**
```sql
-- 从 binlog 反解出被删的行（不改动生产）
mysqlbinlog --no-defaults -vv --base64-output=decode-rows \
  --start-datetime='2026-10-27 10:30:00' --stop-datetime='2026-10-27 10:31:00' \
  --database=<db> binlog.000123 > /tmp/incident.sql
grep -c '^### DELETE FROM' /tmp/incident.sql     -- 影响行数
```
必须给出准确行数与样本，禁止估算。

**第 2 步：选恢复方式（按优先级，代价从低到高）**

| 方式 | 适用 | 代价 | 说明 |
|:---|:---|:---|:---|
| 1. `ROLLBACK` 未提交事务 | 事务未提交 | 几乎为零 | 立刻查 `innodb_trx` |
| 2. 延迟从库回退 | 有 `SOURCE_DELAY` 从库且未过期 | 低 | 前提：平时就有延迟从库（否则写进改进项） |
| 3. 从从库/缓存/下游数仓反查 | 从库尚未回放该语句（时间窗口极短） | 低—中 | 需要"抢在回放前"，实战中常见可行 |
| 4. **binlog 反向生成 INSERT**（`--flashback` 思路） | 有完整 ROW binlog | 中 | 见 [PITR 手册](references/pitr-runbook.md) §闪回；**必须在影子表验证后再回写** |
| 5. **恢复到临时实例后按主键导回**（推荐默认） | 任意有备份+binlog 的场景 | 中—高（耗时看数据量） | 最可控、最不容易二次事故 |
| 6. 生产实例直接 PITR | 极端情况 | 高（会覆盖删除后的正确数据） | ⚠️ 默认禁止，需业务确认丢多少 |

**关键取舍点必须讲给用户**：方式 5/6 的差异在于"**删除之后、恢复之前这段时间的新数据要不要保**"。要保 → 只能走 4 或 5（部分回补）；不要保 → 6 最简单。这个选择必须业务与管理层确认，不是 DBA 单方面决定。

**第 3 步：回写（不可逆动作，全链路要求）**
- 恢复到**独立影子表/临时实例**（命名 `tbl_recover_<date>`），绝不直接在原表操作。
- 校验（行数、主键集合差异、抽样比对、业务字段合计）。
- 回写用 `INSERT ... SELECT` 分批（见 @变更评审 大事务规则），保留原始删除行快照到新表以便二次回退。
- 全程留存证据链：binlog 文件+位点、导出 SQL、校验结果、回写批次记录。

## 路径 A：策略评估

按 [备份策略评估清单](references/backup-strategy-checklist.md) 出结论。核心必答：
- **RPO/RTO 是多少？谁定的？和现在的能力匹配吗？**（多数团队答不上来——这是最有价值的评估产出）
- 备份链是否**闭环**：全备起点 ≤ binlog 起点，binlog 无缺口到当前。（`SHOW BINARY LOGS` 序号连续性 + 全备记录的 LSN/位点）
- 备份**介质与隔离**：是否与生产同机、是否异 site、是否可能被同一场事故一起销毁。
- 备份是否**校验过**：`xtrabackup --prepare` 成功输出、大小/校验和变化、是否有周期性"恢复演练"。
- 恢复演练：最近一次什么时候、恢复耗时（→ 实测 RTO）、结果谁签字。
- 保留策略与合规：日/周/月保留数、是否满足审计与法规要求、历史数据保留期。
- 云 RDS：自动备份窗口、日志备份是否开启、能否下载到本地、跨地域备份、回收站保留期。
- 逻辑备份（mysqldump/mydumper）与物理备份（xtrabackup/云快照）的定位差异：**逻辑备份适合单表/部分恢复与跨版本迁移，物理备份适合整库快速恢复**。只有一种是不足的。

输出格式：**结论（能否满足 RPO/RTO）+ 缺口清单（每条含风险场景与修复动作）+ 演练建议（多久一次、怎么测）**。

## 路径 C：时间点恢复（PITR）

标准链路：**全备 → 应用全备之后的所有 binlog → 停在目标时间点之前**。
详细命令、参数与校验在 [PITR 与误删找回手册](references/pitr-runbook.md)。
必须提前告知的三件事：恢复目标时间点的**确定依据**（业务给出准确时刻/事务标识）、恢复所需**磁盘与时长**、恢复后**如何回补**（新主库数据处理、流量切换）。
恢复必须在**隔离环境**验证一次（新端口/影子实例），确认数据正确再谈切流量。

## 路径 D：单表恢复

前置：`innodb_file_per_table=ON`（独立表空间才可单表导入）。
两条路：
1. `DISCARD TABLESPACE` → 拷贝备份的 `.ibd` → `IMPORT TABLESPACE`（要求表结构完全一致、备份表空间与目标一致；8.0 需处理 `transportable` 标志）。
2. 恢复到临时实例后 `SELECT INTO OUTFILE` / `mysqldump` 单表导入（更稳、更慢）。
外键依赖、触发器、自增值、索引在导入后必须核对。**大表（> 100 GB）导入期间的 IO 与复制影响要提前评估。**

## 一票否决 / 禁忌

- ❌ 在生产实例上直接跑未经验证的恢复脚本；❌ 把恢复动作写成"一条命令搞定"而不留校验点。
- ❌ 未确认备份链闭环就承诺"能恢复到任意时间点"。
- ❌ `RESET MASTER` / 手工删 binlog 文件 / 在未确认下游位点时 `PURGE BINARY LOGS`（等于自毁恢复能力）。
- ❌ 从备份目录直接 `cp` 回生产数据目录（版本、日志序列、表空间 ID 不一致 → 实例起不来或数据错乱）。
- ❌ 未与业务确认"丢不丢删除后的新数据"就开始 PITR。
- ⚠️ 所有涉及覆盖写入的步骤，输出中必须标注不可逆点在第几步。

## If Connectors Available

If **文档平台** 已连接：
- 备份评估报告与恢复方案自动发布；恢复过程记录形成可审计的证据链文档。

If **任务工具** 已连接：
- 演练计划、缺口修复项自动建待办并周期提醒（如"季度恢复演练"）。

If **沟通工具** 已连接：
- 误删场景下把"影响面 + 待确认的取舍"第一时间推给业务与管理层，缩短确认时间。

If **数据库** 已连接（只读账号）：
- 自动核对备份链闭环（binlog 文件与位点连续性）、表行数与自增值、目标表结构一致性。

If 无连接器（默认）：
- 输出评估报告与分步恢复方案到 `outputs/`，命令以可复制代码块给出，校验点逐条列出。
