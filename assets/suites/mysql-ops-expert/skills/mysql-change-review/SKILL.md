---
name: mysql-change-review
version: 1.0.0
description: Review a MySQL change plan (DDL, data migration, parameter tuning, archiving) — assess online-DDL feasibility, locking and space cost, pick gh-ost/pt-osc/native INPLACE, and produce a step-by-step executable plan with rollback and verification.
name_en: Change Review
name_zh: 变更评审
description_en: Review DDL / data migration / parameter / archiving changes: feasibility, lock and space cost, tool choice, executable plan with rollback and verification.
description_zh: 评审 MySQL 变更（DDL、数据迁移、参数调整、数据归档）：在线能力与锁影响、空间与耗时估算、原生 INPLACE / gh-ost / pt-osc 选型，输出可执行变更方案（含回滚与验证）。
user-invocable: true
argument-hint: 贴变更 SQL（如 ALTER 语句）+ 表结构与行数，或贴变更单
argument-hint-en: Paste the change SQL (e.g. ALTER) with table DDL and row count, or the change ticket
argument-hint-zh: 贴变更 SQL（如 ALTER 语句）+ 表结构与行数，或贴变更单
---

# 变更评审

目标：把一句 `ALTER TABLE ...` 变成**能睡着觉上线的变更方案**。评审不通过的，明确给"不通过 + 缺什么信息 + 怎么改能过"。

判读依据：[指标阈值基准](../mysql-ops-knowledge/references/metrics-thresholds.md)
红线与分级：[安全红线与执行分级](../mysql-ops-knowledge/references/safe-execution-rules.md)
索引设计口径：[索引设计手册](../mysql-sql-doctor/references/index-playbook.md)
工具选型：[在线 DDL 工具选型](references/online-ddl-tooling.md)
输出格式：[变更方案模板](references/change-plan-template.md)

## 输入识别

| 用户给什么 | 做什么 |
|:---|:---|
| 一条 `ALTER` | 走完整评审（7 步） |
| 一批 DDL（发版脚本、Flyway/Liquibase 迁移文件） | 逐条评审 + 给**合并/排序建议**（同表多个 ALTER 合并成一次，避免多轮全表重建） |
| 数据订正 SQL（`UPDATE`/`DELETE` 带条件） | 重点走"大事务与分批"路径 |
| 参数变更 | 走"参数变更"专用路径（动态 vs 需重启、主从顺序、回退） |
| 归档/清理方案 | 重点走空间回收与删除节奏 |
| 只有"想加个字段"的想法 | 先补信息采集清单 |
| 已写好的变更单 | 做**合规检查**（逐项打勾，找缺失项），不是重写 |

## 评审 7 步

### 1. 变更分类与风险起点
先定基线风险，决定后续严格程度：

| 类别 | 默认风险 | 说明 |
|:---|:---|:---|
| 加二级索引 | 中 | 多数可 `INPLACE`，占空间 + IO |
| 加列（非末尾/带默认值） | 中—高 | 8.0 `INSTANT` 有条件；5.7 全表重建 |
| 改列类型 / 字符集 / 收窄长度 | **高** | 通常 COPY 全表重建，且可能截断数据 |
| 删列 / 改名 | 高（**常不可逆**） | 应用回滚困难 |
| 加/删主键 | **高** | 复制、恢复、订正能力受影响 |
| 分区改造 / `OPTIMIZE` / 表重建 | 高 | 空间峰值需 2 倍余量 |
| 数据订正（DML） | 中—高 | 大事务 → undo、复制延迟、回滚耗时 |
| 参数变更 | 视参数 | 分动态/重启，分主从顺序 |
| 数据库/表删除 | **极高（L3）** | 必须有备份可用性与演练证据 |

### 2. 可行性与执行方式判定（最关键）
按 [在线 DDL 工具选型](references/online-ddl-tooling.md) 判定：
- 能否 `ALGORITHM=INSTANT`（8.0.12+ 加列到末尾等；**注意：INSTANT 后表可能有行格式碎片，多次 INSTANT 累积影响后续 DDL**）
- 能否 `ALGORITHM=INPLACE, LOCK=NONE`（加索引、部分改类型）
- 只能 `COPY`（改主键、部分改类型、5.7 某些场景）→ **大表必须走 gh-ost / pt-osc**
- 判定口径：`表行数 × 行大小` 与**变更方式**共同决定耗时。**默认阈值：预计执行 > 30 min 或表 > 1000 万行 / > 10 GB，一律按"需影子表工具 + 变更窗口 + 值班陪同"处理。**
- 明确给出耗时估算公式与代入过程，不要只写"预计 1 小时"。

### 3. 空间与 IO 影响
- 新索引/新表体积估算；是否需要 2 倍临时空间（COPY 类、`OPTIMIZE`）。
- 当前磁盘余量是否满足（**磁盘 < 变更所需峰值空间 = 直接不通过**，这是最常见的翻车点）。
- 变更期间 IO 抬升对同机其他实例的影响；云 RDS 是否触发 IO 突发额度耗尽。
- binlog 产出量（RBR 下大表重建可能产生几十 GB binlog → 影响从库延迟与下游同步、磁盘）。

### 4. 复制与下游影响
- 从库延迟预计（主库执行完才开始回放，**从库延迟 ≈ 主库执行耗时**是通用近似）。
- 是否有 DTS/Canal/Kafka/数仓订阅：改列名/类型/删列会打断链路（必须提前通知并在下游验证）。
- `binlog_format=ROW` + `binlog_row_image=FULL` 下大表变更的 binlog 放大。
- 多从库/级联复制的传播时间。

### 5. 业务影响与窗口
- 元数据锁（MDL）风险：**变更开始与结束瞬间需要拿 MDL 写锁**，若此时有长查询/未提交事务会阻塞并引发连锁排队。→ 前置检查必含"当前无 > N 秒的事务/查询"。
- 是否需要停写？停多久？读写分离流量如何摘？
- 建议窗口：**业务低谷 + 避开批处理/结算/备份任务 + 避开周五与发布日**。
- 应用侧兼容性：新代码读旧表结构 / 旧代码读新表结构（**必须支持双向兼容**，这是回滚可行的前提）。

### 6. 回滚方案（评审一票否决项）
按可行性分级：
- **可回滚**：加索引（`DROP INDEX`，INPLACE 快）、加可空列（保留不删即可）。
- **部分回滚**：改类型（需重建回去，耗时同量级）、数据订正（需备份原值）。
- **不可逆**：删列、收窄类型导致截断、`DROP TABLE`。→ **必须给补偿设计**：
  - 采用**两阶段**：先加新列双写 → 迁数据 → 校验 → 切读 → 观察一个周期 → 再删旧列；
  - 删除类变更延后一个版本执行，本期只停用不删除。
- 数据订正必须"**先 SELECT 出将被改的行并存入影子表**"，回滚即从影子表恢复。

### 7. 输出方案
按 [变更方案模板](references/change-plan-template.md) 产出，必含：前置检查清单（带命令）、执行步骤（分步可中断 + 每步观测点与判停标准）、回滚步骤、验证方法、应急联系人、时间预算、失败处理决策树（"跑到一半很慢怎么办"——多数方案缺这一节，恰恰最容易出事）。

## 一票否决清单（任一项即"不通过"）

- ❌ 无回滚方案，或回滚方式与影响面不匹配
- ❌ 未提供表行数/数据量（无法评估耗时与空间）
- ❌ 磁盘余量不足峰值需求
- ❌ 长事务防护缺失（未设 `lock_wait_timeout`、无 kill 长查询前置步骤）
- ❌ 大表（> 1000 万行）用 COPY 方式在主库直接执行
- ❌ 无 binlog/下游同步链路影响评估（有订阅时）
- ❌ 变更窗口在业务高峰或周五/发布日且无理由说明
- ❌ 删列/删表类变更未采用两阶段（本期删除）
- ❌ 未在从库或影子表做过一次演练

## 大事务/数据订正专项规则

`UPDATE`/`DELETE` 满足任一即必须分批：影响行数 > 10 万、预计耗时 > 5 min、从库会因此延迟 > 30s、undo 空间增长可观。
分批模板：
```sql
-- 循环执行直到 affected rows = 0，每批之间 sleep 0.2–0.5s 观察复制延迟
DELETE FROM <tbl> WHERE <cond> AND id BETWEEN :a AND :b LIMIT 2000;
```
并给出：批次大小依据、进度可观测方式（记录已处理最大 id）、中断是否安全（幂等条件）、预计总时长。

## 参数变更专项路径

必须说明：当前值 → 目标值 → 依据（哪个指标）→ 动态生效还是需重启 → 从库先改还是主库先改（**通常先从库，验证后再主库，且需重启的参数要评估滚动重启顺序**）→ 是否写入配置文件/`SET PERSIST`（防止重启回退）→ 回滚命令 → 观察指标与判停标准。
云 RDS：需在参数模板下发，注意"可修改参数"范围与"是否重启"标记。

## 边界

- 只做方案与评审，不替用户执行变更。
- 不因为"INPLACE 不会锁表"就忽略 MDL 与从库延迟——这两点必须在方案里量化。
- 用户催"直接告诉我能不能执行"时，先给结论（通过/有条件通过/不通过）再给依据，但**有条件通过必须列明条件**。

## If Connectors Available

If **数据库** 已连接（只读账号）：
- 自动采集表行数、数据/索引体积、磁盘余量、当前长事务，评审结论直接带实测值。

If **文档平台** 已连接：
- 变更方案自动发布为文档并挂审批流，评审意见沉淀在同一文档内。

If **任务工具** 已连接：
- 按方案步骤生成上线 checklist 待办；变更后 24h 的"回退临时措施"提醒自动排期。

If **沟通工具** 已连接：
- 变更开始/结束/异常自动播报到群，值班期间进度可视。

If 无连接器（默认）：
- 输出变更方案到 `outputs/change-plan-<表名>-<YYYYMMDD>.md`，前置检查命令供复制执行。
