---
name: mysql-incident-triage
version: 1.0.0
description: Handle a live MySQL incident — classify the symptom, walk the matching decision tree to find root cause, propose safe mitigation first, then produce a timeline-based postmortem with action items.
name_en: Incident Triage
name_zh: 故障应急
description_en: Classify a live MySQL incident, walk the matching decision tree to root cause, propose safe mitigation first, then produce a timeline postmortem.
description_zh: 线上故障应急：按现象分类进入对应决策树定位根因，先止血再根治，所有动作按风险分级标注，事后输出时间线复盘与改进项。
user-invocable: true
argument-hint: 描述现象（如"主库 CPU 100%，大量超时"）+ 贴 processlist/错误日志
argument-hint-en: Describe the symptom (e.g. "primary CPU 100%, timeouts") + paste processlist / error log output
argument-hint-zh: 描述现象（如"主库 CPU 100%，大量超时"）+ 贴 processlist/错误日志
---

# 故障应急

**核心原则：先止血，再根治；先保数据，再保可用。** 应急场景下允许输出 L2 临时措施，但必须同时给出回退命令，并标注"恢复后必须回退基线"。

判读依据：[指标阈值基准](../mysql-ops-knowledge/references/metrics-thresholds.md)
定位路径：[现象→根因决策树](../mysql-ops-knowledge/references/diagnostic-decision-tree.md)
取数命令：[只读诊断命令清单](../mysql-ops-knowledge/references/command-cheatsheet.md)
红线与分级：[安全红线与执行分级](../mysql-ops-knowledge/references/safe-execution-rules.md)
详细处置：[场景 Runbook 集](references/runbooks.md)、[复盘模板](references/postmortem-template.md)

## 第一步：定级（10 秒内完成，不追求准确）

| 级别 | 判据 | 节奏 |
|:---|:---|:---|
| **P0** | 实例不可用 / 核心读写大面积失败 / 疑似数据丢失或不一致 | 立刻拉人，止血优先，禁止"先分析清楚再动" |
| **P1** | 明显劣化（大面积超时、延迟飙升）但业务可降级 | 5 分钟内给止血动作 |
| **P2** | 单点变慢、非核心链路、有冗余 | 按巡检问题清单流程处理 |

同时确认三件事（一句话问清，不要连环追问）：**影响范围**（哪些库表/业务）、**开始时间**（决定对齐哪次变更）、**拓扑**（主从/多写/云 HA 是否已切换）。

## 第二步：保全现场（在采取任何止血动作之前）

这是应急中最容易被跳过、代价最高的一步。给出**一条组合命令**让用户一次抓全：

```bash
# [L0] 现场快照：30 秒内可完成，先抓再动手
TS=$(date +%Y%m%d_%H%M%S); D=/tmp/inc_$TS; mkdir -p $D
{ mysql -e "SHOW FULL PROCESSLIST"; mysql -e "SHOW ENGINE INNODB STATUS\G";
  mysql -e "SHOW GLOBAL STATUS"; mysql -e "SELECT * FROM information_schema.innodb_trx";
  mysql -e "SHOW REPLICA STATUS\G"; mysql -e "SHOW BINARY LOG STATUS";
  dmesg -T | tail -200; uptime; iostat -x 1 3; vmstat 1 3; df -hT;
  tail -300 "$(mysql -sN -e 'SELECT @@log_error')"; } > $D/snapshot.txt 2>&1
echo "现场已保存：$D/snapshot.txt"
```

**禁忌**：`KILL` 掉所有连接、`RESTART` 实例、清理日志——这三件事都会毁灭性破坏现场。特别是重启：崩溃恢复的现场一旦重启，根因基本无法定位，且可能触发二次故障。

## 第三步：分类进入决策树

| 现象关键词 | 进入 | 首选止血 |
|:---|:---|:---|
| CPU 高 / load 高 | T1 | 杀 Top 只读查询、限流来源 |
| `Too many connections` / 连接耗尽 | T2 | 清理异常 Sleep、临时上调上限（算内存总账） |
| 大量"锁等待超时" / `Deadlock found` | T3 | 处理**持锁方**而非等待方 |
| 整体变慢、慢查询暴增 | T4 | 定位环境变化（变更/发布/备份/统计信息） |
| 单条 SQL 慢 | T5 | 改写 / `FORCE INDEX` 局部兜底 |
| IO 打满 / await 高 | T6 | 杀扫描型查询、错峰任务、临时提升规格 |
| 主从延迟 / 数据不一致 | T7 | 关键读切主库、开并行复制、暂停从库任务 |
| 磁盘满 / 实例变只读 | T8 | 清 binlog、关 general log、扩容 |
| 内存告警 / OOM | T9 | 降并发、回收会话、核对内存总账 |
| 起不来 / 反复重启 / 疑似数据损坏 | T10 | **先物理备份**，再谈 `innodb_force_recovery` |

**现象不明时**按通用归因顺序排除：资源 → 锁与事务 → 执行计划 → 流量热点 → 配置漂移 → 拓扑复制 → 版本 Bug。

**必问的一条**：故障时间点前后 2 小时内有没有变更（发布、DDL、参数、扩缩容、HA 切换、定时任务）？统计显示多数故障与近期变更相关，先排除这条比任何深奥分析都高效。

## 第四步：止血动作的输出格式

每个动作都按这个结构给，缺一不可：

```
动作 N：<一句话>
目的：<解除什么现象>
命令：```sql ... ```   -- [L2] 需审批
前置检查：<跑什么确认安全，例如先看该会话是否在改数据>
预估影响：<耗时/是否影响写入/回滚代价>
观察指标：<看什么、多久生效、什么值算止住>
回退：<恢复基线的具体命令>
不可逆点：<若存在，明确写出>
```

**数据保护优先级高于可用性**：任何可能造成数据丢失的选择（跳过复制事件、`innodb_force_recovery` ≥3、未确认下游位点的 `PURGE BINARY LOGS`、未备份的重启）都必须显式标注"⚠️ 可能丢数据/造成不一致"并给出替代路径。

## 第五步：判定"是否真的恢复了"

不能只看现象消失。给出验证清单：
- 关键指标回到基线（列出具体指标与基线值）
- 数据一致性校验（有主从时：GTID 集合比对 / 关键表行数与校验和）
- 应用侧错误率/超时归零，且观察 ≥ 15 分钟
- **临时措施是否已登记待回退**（最常被遗忘的一环）

## 第六步：复盘

故障恢复后主动提议产出复盘报告，按 [复盘模板](references/postmortem-template.md)：时间线（含每个动作的效果证据）、根因（5 Why 到可执行层）、影响量化、止血为什么慢、改进项（预防 / 检测 / 处置三类，每条有责任人和验收标准）。

复盘的归因必须区分 **直接原因 / 促成因素 / 根因 / 检测缺失**。只写"某条 SQL 没走索引"不算根因——要回答"为什么没被拦住"。

## 边界与禁忌（本技能绝不做的事）

- ❌ 不建议未做物理备份就执行 `innodb_force_recovery`、表重建、`DROP`。
- ❌ 不建议 `rm` 任何数据目录文件、binlog、undo、`#sql-*`。
- ❌ 不建议在从库 `read_only=OFF` 写数据、`sql_replica_skip_counter` 跳过事件（GTID 下不可用且致不一致）。
- ❌ 不建议"重启看看"作为主要处置手段。
- ❌ 不建议全局 `optimizer_switch` 修改或一次性 `KILL` 全部连接。
- ❌ 不臆测根因。证据不足时明确说"当前只能排除 X/Y，需补采 Z"，并给采集命令。
- ⚠️ 涉及丢数据风险的决策，输出中必须提示"需业务与管理层确认后再执行"。

## If Connectors Available

If **沟通工具** 已连接：
- 自动把"当前判定 + 止血动作 + 待确认项"推送到应急群，减少故障期间的信息搬运。

If **监控指标** 已连接：
- 拉取故障窗口曲线自动对齐变更时间线，直接给出指标恶化起点，省去人工截图比对。

If **文档平台** 已连接：
- 故障期间自动创建实时作战文档（时间线随处置进展追加），复盘报告直接发布。

If **任务工具** 已连接：
- 复盘改进项自动建待办并指派，超期提醒；临时措施登记为"待回退"任务。

If 无连接器（默认）：
- 会话内输出止血清单 + 落盘 `outputs/incident-<现象>-<YYYYMMDD>.md`，复盘报告同样落盘。
