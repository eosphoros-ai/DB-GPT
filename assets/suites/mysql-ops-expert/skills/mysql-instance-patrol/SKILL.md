---
name: mysql-instance-patrol
version: 1.0.0
description: Run a structured health patrol over a MySQL instance — resources, connections, locks, replication, space, schema risks and config drift — producing a graded report with an actionable issue list and owners.
name_en: Instance Patrol
name_zh: 实例巡检
description_en: Structured health patrol over resources, connections, locks, replication, space, schema risks and config drift, with a graded actionable report.
description_zh: 对 MySQL 实例做结构化体检：资源、连接、锁与事务、复制、空间、Schema 风险、配置漂移，输出红黄绿分级报告与可认领问题清单。
user-invocable: true
argument-hint: 贴 SHOW GLOBAL STATUS / 巡检 SQL 结果，或说"给一份巡检采集脚本"
argument-hint-en: Paste SHOW GLOBAL STATUS / patrol SQL output, or ask for a collection script
argument-hint-zh: 贴 SHOW GLOBAL STATUS / 巡检 SQL 结果，或说"给一份巡检采集脚本"
---

# 实例巡检

目标：一次巡检产出的不是一堆指标，而是**带优先级、能认领的问题清单**。每个红/黄项都必须有依据数值、影响判断和下一步动作。

判定阈值一律以 [指标阈值基准](../mysql-ops-knowledge/references/metrics-thresholds.md) 为准；命令取自 [只读诊断命令清单](../mysql-ops-knowledge/references/command-cheatsheet.md)；输出前的安全自检见 [安全红线与执行分级](../mysql-ops-knowledge/references/safe-execution-rules.md)。

## 先判断走哪条路径

| 用户给的东西 | 走法 |
|:---|:---|
| 什么都没给，只说"帮我巡检" | **路径 A：先给采集包**（一次性给全，不挤牙膏） |
| 贴了 `SHOW GLOBAL STATUS` / 巡检 SQL 结果 | **路径 B：直接分析** |
| 只有云监控截图/CSV 导出 | **路径 B**，指标缺失项写进"待采集" |
| 要定期巡检（每天/每周自动跑） | **路径 C：巡检方案 + 定时任务** |
| 明确说"线上出问题了" | 停止巡检流程，转 **@故障应急**（巡检是找隐患，不是救火） |

## 路径 A：输出采集包

按 [巡检清单](references/patrol-checklist.md) 生成一份可直接执行的采集脚本，要求：
- 全部 🟢 L0 只读命令，标注"建议在主库执行"（多数视图主从都有差异，需主从各跑一次）。
- 明确提示两次采样算速率的做法（`SHOW GLOBAL STATUS` 单次是累计值，**不能直接判读增量类指标**——这是巡检最常见的错误）。
- 云 RDS 无 OS 权限时，给出控制台/监控 API 需要导出的指标名清单。
- 输出重定向到带时间戳的文件，便于归档与两次对比。

一次性给全，然后告诉用户："跑完把文件贴回来（或放到工作目录），我按清单逐项判读。"

## 路径 B：判读（核心）

按 8 个域逐项过，**每个域都要给出结论，即使正常也要写"正常，依据 X"**（避免"没报就是没问题"的误解）：

1. **可用性与重启线索** — `Uptime` 异常短必须查错误日志；`Com_select` 等计数器归零说明重启过。
2. **资源层** — CPU（区分 us/sy/wa）、内存是否算得过来总账、IO util/await、磁盘余量与增长斜率、fd。
3. **连接与线程** — 使用率、`Threads_running`、来源分布、异常 Sleep、`Aborted_*` 增速。
4. **锁与事务** — 行锁等待/死锁计数、当前长事务、未提交事务持 MDL、history list length。
5. **InnoDB 健康** — BP 命中率、脏页与刷盘、`buffer_pool_wait_free`、redo 等待、读放大。
6. **复制与高可用** — 双线程状态、真实延迟（区分 `Seconds_Behind_Source` 的局限）、并行度、GTID 一致性、从库 `read_only`、半同步降级。
7. **空间与对象风险** — Top 大表、碎片率、binlog/undo/tmp/日志占用、无主键表、自增余量、超大字段、字符集混用。
8. **配置漂移与安全** — 运行时值 vs 配置文件值、主从关键参数一致性、`sql_mode` 严格性、高危账号、慢日志是否开启、备份策略是否落在窗口内。

每项输出格式：**判定（红/黄/绿）+ 实测值 + 阈值依据 + 影响 + 下一步动作（含 L 级打标）**。

## 严重度与优先级规则

- 🔴 **红**：命中"继续恶化即影响可用性/数据" → 24h 内处理，进问题清单 P0。示例：磁盘 > 85%、复制线程中断、BP 命中率 < 99% 且 IO 打满、存在无主键大表 + 需 PITR。
- 🟡 **黄**：有明确劣化路径但短期无影响 → 排期处理 P1/P2。
- 🟢 **绿**：留档，用于下次趋势对比。

**趋势优先于瞬时值**：单次 `df` 80% 不如"7 天增速 2%/天，5 天后触顶"重要。有历史数据时必须给增长预测与触顶日期。

## 输出

按 [巡检报告模板](references/patrol-report-template.md) 组织，落盘 `outputs/patrol-<实例名>-<YYYYMMDD>.md`。
报告必须包含：
- **执行摘要**（3–5 行：整体健康度评级、最危险的 2–3 项、必须本周做的事）
- 逐域判读表
- **问题清单**（可认领：编号、问题、影响、建议动作、风险等级、建议责任方、优先级）
- 待采集项（明确命令）
- 与上次巡检的 diff（有历史时）
- 可信度声明（数据来源与时间范围）

问题清单要写成**能直接转工单的粒度**——每条自带表名/SQL/参数名，而不是"存在慢查询"。

## 路径 C：常态化巡检

1. 输出固定采集脚本 + 判读标准，形成"人跑一次即得报告"的闭环。
2. 建议用定时任务在固定时间自动跑（工作日 09:30 是常见选择），并把报告投递到沟通工具与文档目录。
3. 明确**哪些项交给监控告警**（阈值型：磁盘、延迟、锁等待、连接数）、**哪些只能靠巡检发现**（趋势型与结构型：碎片、无主键、索引冗余、配置漂移）。这条划分能显著降低无效告警。

## 边界

- 巡检不执行任何变更。所有修复动作转交 **@SQL 体检** / **@参数调优** / **@变更评审**。
- 不凭单点数据下"没问题"的结论；采集不到的指标进"待采集"，不用默认值代替。
- 多个实例巡检时逐实例出报告，最后加一份横向对比（配置差异、容量差异、参数漂移矩阵）——**参数漂移矩阵是多实例场景最高价值的产出**。

## If Connectors Available

If **数据库** 已连接（只读账号）：
- 直接执行采集包并解析结果，无需用户粘贴；支持多实例批量巡检与历史对比。

If **监控指标** 已连接：
- 自动取 7/30 天趋势曲线做增长预测，替代人工截图。

If **文档平台** 已连接：
- 报告自动发布到巡检目录，保留历史版本形成趋势档案。

If **任务工具** 已连接：
- 问题清单逐条建待办并指派责任方，超期未完成自动提醒。

If **沟通工具** 已连接：
- 报告摘要（红黄项 + 本周待办）推送到 DBA/研发群，全文以链接给出。

If 无连接器（默认）：
- 生成采集脚本与报告文件到 `outputs/`，用户在会话中粘贴采集结果完成闭环。
