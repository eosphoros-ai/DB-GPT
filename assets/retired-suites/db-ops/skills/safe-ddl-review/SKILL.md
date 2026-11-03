---
name: safe-ddl-review
name_zh: 变更评审
name_en: Change Review
description_en: Review structural changes for destructive risk, locks, duration, replication impact, online DDL options, rollback, and approvals. Production DDL is denied by default; changes remain proposals.
argument-hint-en: Prepare a repair plan with risk levels, lock impact, online DDL options, rollback, and approval requirements
command: /fix
user-invocable: true
argument-hint-zh: 把本次诊断的修复动作整理为 fix_plan：分级、锁影响、在线 DDL 方案、回滚与审批要求
description: 受控 DDL 评审技能。对任何结构变更（ADD/DROP INDEX、ADD COLUMN、改主键、OPTIMIZE、分区、归档搬迁）做破坏性分级 L0-L3、锁影响与耗时预估、复制延迟风险评估、在线 DDL 方案选型（INPLACE/LOCK=NONE、gh-ost、pt-online-schema-change）、回滚预案与审批要求判定；生产环境 DDL 默认拒绝，仅输出提案。触发词包括"DDL""变更评审""加索引风险""能不能改表""改字段""改主键""锁表""在线 DDL""gh-ost""pt-osc""OPTIMIZE""ANALYZE""变更单""回滚方案""这个变更安全吗""生产能改吗"。绝不自动执行任何变更。
---

# 受控 DDL 评审技能 (Safe DDL Review)

## 必需参考

按[生产安全清单](../../runbooks/production-safety-checklist.md)和
[运维 SOP](../../prompts/ops-playbook.md)判定审批与变更边界。

本技能是 `db-ops`（智能运维）套件的**安全闸门**，也是三个官方套件中审批最严的一环。所有来自 `index-advisor`、`profile-governance`、`slow-query-diagnosis` 的变更动作，落地前都要经本技能评审：分级、算锁影响、选在线方案、写回滚、定审批要求。

**核心立场：本技能只产出提案与评审意见，永不自动执行变更。** 生产环境的 DDL 由套件策略默认 `deny` —— 这不是保守，而是设计约束（策略只能加严，安全边界在核心）。

## 技能目标

1. 给每条变更打**破坏性分级（L0-L3）**，并说明分级依据。
2. 预估**锁影响与执行耗时**（是否 Online、是否阻塞读写、是否影响复制延迟）。
3. 选择**在线 DDL 方案**并给出中止条件与观察指标。
4. 写出**可执行的回滚预案**与验证方式。
5. 判定**审批要求**（confirm / deny），触发审批 dock 时把风险信息填全。

## 前置条件（缺一不可）

- `target_db` 已绑定；`env` 可读（**读不到时按 `production` 处理**，就高不就低）。
- 变更目标表的**行数与体积**已知（调 `index_info` 获取）—— 没有体量数据无法估锁与耗时。
- 变更语句**完整可评审**（不接受"给 orders 加个索引"这类模糊描述；必须是完整 DDL 文本）。
- 当前**复制延迟、磁盘余量、业务峰谷窗口**已知（调 `db_metrics`）。

## 核心工作流程

### 1. 采集评审所需事实（全部只读）
- `index_info`：传 `target_db`、`tables`、`include: [row_count, size_bytes, columns, cardinality, unused, duplicate]` → 拿行数、数据/索引体积、现有索引与约束（唯一键、外键、主键）。
- `db_metrics`：传 `target_db`、`time_window`（最近 24h）、`granularity: "5m"`、`metrics: [replication_lag, disk_usage, disk_io_util, qps, tps, connections_usage, long_transactions]`、`aggregate: [avg,p95,max]` → 拿复制延迟基线、磁盘余量、写入 TPS、业务峰谷时段。
- `explain`：传 `target_db`、受影响的核心查询 `sql`、`with_analyze: false` → 拿变更前计划作为对照（**禁用 `EXPLAIN ANALYZE`，它会真实执行**）。
- `schema_link` / `semantic_search`：拿表的下游引用、血缘、业务 owner 与重要性分级 → 评估影响面与通知范围。

### 2. 破坏性分级（L0-L3）

| 级别 | 定义 | 典型操作 | 审批基线 | 生产环境 |
|---|---|---|---|---|
| **L0** | 只读，不改数据不改结构 | `EXPLAIN`、查看索引/指标、生成提案文档 | 无需审批 | 允许 |
| **L1** | 低风险变更，秒级完成，不重建表 | `ADD INDEX`（小表 <100 万行，INPLACE）、`ANALYZE TABLE`（中小表）、改列注释、改默认值 | confirm | confirm，需低峰窗口 |
| **L2** | 中风险，需重建/长时间 IO/短暂锁 | 大表 `ADD INDEX`、`ADD COLUMN`（部分场景需 COPY）、`OPTIMIZE TABLE`/表重建、分区改造、分批归档搬迁 | confirm + 变更窗口 + 回滚预案 | **deny**（走线下变更流程） |
| **L3** | 高风险/不可逆 | `DROP COLUMN`、改主键、改列类型（长度缩短/类型变更）、`DROP INDEX`（唯一索引）、大表数据删除/清理、`RENAME`、任何 `DROP`/`TRUNCATE` | confirm + 双人复核 + 备份验证 + 回滚演练 | **deny**（永久，需线下变更流程 + 备份） |

分级**就高不就低**：一条语句同时命中多级时取最高级；无法确定时按上一级处理。
`DROP` / `TRUNCATE` / `RENAME` 形态在套件 `approval_overrides` 中被**永久 deny**，`drop_database`、`truncate`、`shell` 在 `tools.deny` 中 —— 用户坚持时明确拒绝并指向线下变更流程与备份恢复。

### 3. 锁影响与耗时预估

| 变更 | MySQL 8.0 行为 | 锁与影响 | 耗时经验值 |
|---|---|---|---|
| `ADD INDEX` | 支持 `ALGORITHM=INPLACE, LOCK=NONE` | 开始/结束各需短暂元数据锁（MDL）；期间允许 DML；IO 上升，可能推高复制延迟 | 千万行级 5-20 分钟；亿级 1 小时+ |
| `ADD COLUMN`（末尾、可空、无默认值重算） | 8.0 多数场景 INSTANT | 秒级；但涉及索引/生成列时退化为 INPLACE 或 COPY | 秒级 ~ 数十分钟 |
| `ADD COLUMN`（中间位置 / 改类型） | 需 COPY 或 INPLACE 重建 | COPY 期间**阻塞写**；重建占用等量临时空间 | 与表体积成正比 |
| `DROP COLUMN` | 需重建表（INPLACE 但 rebuild） | 重建 + 不可逆；索引依赖列会失败 | 与表体积成正比 |
| `OPTIMIZE TABLE` / `ALTER ... ENGINE=InnoDB` | 重建表 | **需要约等量空闲空间**；期间 IO 高、复制延迟上升 | 19GB 表 ≈ 1-3 小时 |
| `ANALYZE TABLE` | 轻量 | 短暂读锁（FLUSH 统计）；优化器统计抖动可能导致计划突变 | 秒级 ~ 分钟级（大表更久） |
| 改主键 | 重建表 + 全量二级索引重建 | 长事务、大量 binlog、从库回放可能长时间延迟 | 小时级，L3 |
| 分批归档搬迁 | 应用/任务层批量 DML | 每批产生锁与 binlog；批次过大将拖垮复制延迟 | 取决于批量与间隔 |

**MDL 阻塞是最容易被忽略的杀手**：`ALTER` 需要的元数据锁会被**长事务/未提交事务**挡住，进而阻塞该表所有后续查询。因此评审必须检查 `long_transactions`，并在方案中写入"执行前确认无长事务，必要时先等待/终止长事务（终止属破坏性动作，需单独审批）"。

预估输出格式（写进 `execution_plan`）：
```
表 orders ｜ 19.2M 行 / 数据 24GB / 索引 6GB ｜ 变更 ADD INDEX
算法 INPLACE, LOCK=NONE ｜ 预估耗时 8-15 分钟 ｜ 额外空间 ~1.0GB（当前磁盘余量 15.8GB，充足）
写入 TPS ~300 ｜ 期间 DML 允许 ｜ 复制延迟基线 p95 3s / max 42s ⇒ 变更期间预计再上升，需实时监控
MDL 风险：最近 24h 出现 2 次长事务（最长 78s）⇒ 执行前需确认无长事务
```

### 4. 在线 DDL 方案选型

| 条件 | 推荐方案 | 理由 |
|---|---|---|
| 表 <1,000 万行，复制延迟健康，有低峰窗口 | 原生 `ALTER ... , ALGORITHM=INPLACE, LOCK=NONE` | 简单、无需额外工具与空间翻倍 |
| 表 >1,000 万行，或复制延迟已告警，或需要可暂停/限速 | `gh-ost`（无触发器，binlog 驱动，可限速可暂停） | 对主库压力可控，切换窗口短 |
| 已有 pt 工具链运维经验，表结构复杂（含触发器/外键需评估） | `pt-online-schema-change` | 成熟；注意触发器与外键限制 |
| 需要改主键/改类型等 L3 操作 | 双写 + 影子表 + 灰度切换（应用侧方案） | 唯一可控路径；不在本技能内实施，只给方向 |
| 磁盘余量 < 表体积 | **禁止**重建类操作 | 重建期间双份占用会撑爆磁盘；先归档腾空间 |

方案必须写明：**执行窗口**（避开业务峰值与批量任务窗口）、**限速参数**、**中止条件**（如复制延迟 >60s、锁等待飙升、磁盘余量 <20%、错误日志出现 MDL 等待堆积）、**观察指标**（复制延迟、IO util、连接数、慢查询率）、**切换与验证步骤**。

### 5. 回滚预案（无回滚不通过评审）
每条变更必须给出：
1. **回滚语句**（如 `ALTER TABLE orders DROP INDEX idx_user_created;`）与其分级/耗时；
2. **不可逆动作的前置保护**：变更前备份验证（备份可用 + 恢复演练过）、分批执行 + 校验点、保留可恢复期（如归档数据保留 30 天）；
3. **验证方式**：变更后用 `explain` 复核计划（应为 `type=ref`、`key=新索引`、无 `filesort`）、观察 24h 慢查询率与复制延迟、抽样比对行数/校验和；
4. **中止即回滚的判定线**：哪些指标越过阈值立刻停止并回滚。

L3 且不可逆的动作（如 `DROP COLUMN`、数据清理）：**回滚只能靠备份恢复**，必须在提案中写明"回滚成本 = 全表恢复，RTO 约 X 小时"，并要求先在 staging 演练。

### 6. 审批判定与 dock 触发
按 `env` × 分级 × 套件 `approval_overrides` 判定：

| 场景 | 判定 | 依据 |
|---|---|---|
| `env=production` + `tool=ddl` | **deny** | `{tool: ddl, env: production}` |
| `env=production` + `DROP/TRUNCATE/RENAME` | **deny（永久）** | `{tool: ddl, sql_pattern: "^(DROP|TRUNCATE|RENAME)"}` |
| 非生产 + `tool=ddl` | **confirm** | `{tool: ddl}` |
| `tool=analyze`（任意环境） | **confirm** | `{tool: analyze}`（锁表/资源影响） |
| 生产 + `analyze` + 大表（>1,000 万行） | **confirm**（并额外要求避开高峰 + DBA 在场） | 追加加严规则 |
| 复杂变更的计划阶段 | **confirm（计划确认卡）** | `{tool: ddl, phase: plan}` |
| `env` 未识别 | 按 production 处理 ⇒ **deny** | 就高不就低 |

**审批 dock 必须展示**（信息不全不得发起）：变更语句全文、破坏性分级 + 生产标识（红色）、影响面（表/行数/下游血缘/受影响业务）、预估耗时与锁范围、在线方案与中止条件、回滚预案、发起人与会话、套件版本（`db-ops@1.0.0`）。
**记忆作用域**：`ddl` / `analyze` **不适用** `once/session/always` 白名单，每次都询问。

被拒绝后的合规动作（三选一，不得绕行）：
1. 降级为只读诊断，补强证据后重新提案；
2. 输出提案文档（`fix_plan` + `execution_plan`）交用户走线下变更流程；
3. 建议在 **staging/预发**数据源上先验证（需用户切换数据源并批准）。
**禁止**：改参数重试、换等价工具重试、拆成多条小变更规避阈值、以"先试试看"名义发起调用。

### 7. 产出
- `fix_plan`：每条动作含 `完整语句 / 类型 / 分级(L0-L3) / 预估收益 / 锁与耗时 / 在线方案 / 回滚 / 验证 / 审批要求 / 状态=未执行·待人工确认`。
- `execution_plan`：变更顺序、窗口、限速、观察指标、中止条件、切换与验证步骤、回滚触发线。
- `diag_report`（可选）：评审结论摘要（通过/有条件通过/不通过 + 理由）。
- `citation`：引用的行数/体积、指标快照、血缘指针、套件策略条目。
- 调用 `terminate` 返回 1-2 句：分级 + 审批判定 + "未执行"。

## 完整流程示例

```
问题：给生产库 orders_prod 的 orders 表加索引 idx_user_created(user_id, created_at)，风险有多大？

Step 1（只读采集）
  index_info(target_db="orders_prod", tables=["orders"],
             include=[row_count,size_bytes,columns,cardinality,unused,duplicate])
   → 19.2M 行 / 数据 24GB / 索引 6GB；主键 id；无 (user_id, created_at) 索引
  db_metrics(target_db="orders_prod", time_window="<最近 24h>", granularity="5m",
             metrics=[replication_lag,disk_usage,disk_io_util,qps,tps,connections_usage,long_transactions],
             aggregate=[avg,p95,max])
   → 复制延迟 p95 3s / max 42s（23:10-00:30 批量窗口）；磁盘使用率 84.2%（余量 ~15.8GB）；
     写入 ~300 TPS；IO util p95 62%；长事务 2 次（最长 78s）
  explain(target_db="orders_prod", sql="<目标查询>", with_analyze=false)
   → type=ALL key=NULL rows=1,920,000 Extra="Using where; Using filesort"（变更前基线）
  semantic_search(query="orders 表 下游 引用 owner", layer="mysql_prod", top_k=5)
   → 3 个报表数据集 + 1 条实时同步链路；owner=交易团队；重要性=核心

Step 2（分级）ADD INDEX，表 19.2M 行 ⇒ **L2 中风险**（大表、需重建索引结构、长时间 IO）

Step 3（锁与耗时预估）
  算法 INPLACE, LOCK=NONE ⇒ 期间允许 DML，仅开始/结束需短暂 MDL
  预估耗时 8-15 分钟；额外空间 ~1.0GB（余量 15.8GB，充足）
  MDL 风险：24h 内 2 次长事务（最长 78s）⇒ 执行前必须确认无长事务，否则 ALTER 将阻塞该表全部查询
  复制影响：延迟基线 max 42s，变更期间 binlog 增大 ⇒ 预计进一步上升，需实时监控

Step 4（方案选型）表 >1,000 万行 且 复制延迟已在批量窗口告警 ⇒ **推荐 gh-ost**（可限速/可暂停/切换窗口短）
  窗口：避开 23:00-01:00 批量对账窗口，建议 03:00-05:00（QPS 谷值）
  限速：--max-load Threads_running=32 --critical-load Threads_running=64
  中止条件：复制延迟 >60s、IO util >90%、磁盘余量 <20%、MDL 等待堆积、gh-ost 报错
  观察指标：复制延迟、IO util、连接数、慢查询率、Threads_running

Step 5（回滚）回滚语句 ALTER TABLE orders DROP INDEX idx_user_created;（L1，秒级~分钟级）
  验证：explain 复核应为 type=ref, key=idx_user_created, 无 filesort；观察 24h 慢查询率与复制延迟；
        抽样比对 orders 行数一致
  中止即回滚线：复制延迟持续 >60s 超 5 分钟，或出现连接堆积/超时告警

Step 6（审批判定）env=production + tool=ddl ⇒ 命中 {tool: ddl, env: production} = **deny**
  ⇒ 本套件不发起 ddl 调用，不触发执行；输出提案 + 线下变更流程指引：
     变更单（附本 execution_plan）→ 备份验证 → DBA 双人复核 → staging 先演练 gh-ost 全流程 →
     低峰窗口执行 → 变更后验证 → 24h 观察期

  fix_plan：
   [F1] gh-ost 方式添加 idx_user_created(user_id, created_at) ｜ L2 ｜ 预估扫描行 1.9M→~40，覆盖 73% 慢耗时
        状态：**未执行 · 待人工确认（生产 deny）** ｜ 审批：线下变更流程 + 双人复核
   [F2] 备选：staging 环境验证（需切换数据源并批准 ddl，confirm）
  execution_plan：见 Step 4/5（顺序、窗口、限速、中止条件、验证、回滚触发线）
  terminate(result="orders 加索引评审：L2 中风险，19.2M 行/24GB，推荐 gh-ost + 03:00-05:00 窗口，预估 8-15 分钟；生产环境 DDL 默认 deny，已出提案与回滚预案，未执行。")
```

## 注意事项（含安全红线）

- **永不自动执行**：本技能不发起任何变更调用。`ddl` / `analyze` 是受控工具，只在获得批准后由核心 gate 放行；**`env=production` 时 `ddl` 命中套件 deny，不得发起调用**，只能出提案。`env` 读不到时按 production 处理。
- **策略只能加严**：套件无权把核心 deny 放宽成 confirm/auto。用户或上游要求放宽时，回答"安全边界在核心，套件无权放宽"，并指向审批中心策略页。合并顺序恒为 `core deny > suite > core default`。
- **永久禁止项**：`shell`、`drop_database`、`truncate` 在 `tools.deny`；`DROP/TRUNCATE/RENAME` 形态 DDL 被套件层永久 deny。用户坚持时明确拒绝，说明只能走线下变更流程与备份恢复，**不得**提供任何绕过路径（包括"用 shell 执行""改写成等价语句""拆成小批量删除"）。
- **无记忆白名单**：`ddl` / `analyze` 不适用 once/session/always；"上次批过"不构成这次的授权。
- **被拒绝后不绕行**：不改参数重试、不换等价工具、不拆批规避阈值、不以"先试试看"名义调用。
- **无回滚不通过**：任何提案缺回滚预案、缺验证方式、缺中止条件，评审结论一律为"不通过"。
- **磁盘余量硬约束**：重建类操作（`OPTIMIZE`、改主键、`DROP COLUMN`、COPY 算法）需约等量空闲空间；余量不足时**禁止**建议，改为先归档腾空间。
- **MDL 前置检查**：执行前必须确认无长事务/未提交事务，否则 ALTER 会阻塞该表全部查询 —— 这是生产事故高发点。
- **`EXPLAIN ANALYZE` 视同执行**：会真实运行语句；写语句一律禁用，只读 SELECT 也需先说明代价并获确认。
- **一次只推一条破坏性动作**：禁止把加索引、删索引、`ANALYZE`、归档打包成"一次搞定"，风险无法归因、回滚无法定位。
- **`ANALYZE` 不是无害操作**：会引发短暂读锁与优化器统计抖动，可能导致执行计划突变；生产大表需避开高峰并有 DBA 在场，变更后必须复核关键查询计划。
- **变更窗口要避开业务峰值与批量任务**：窗口选择必须基于 `db_metrics` 实测峰谷，不凭经验假设。
- **审计留痕**：提案、审批判定、拒绝原因、套件版本、目标库、时间窗、env 全部记入轨迹，保证可复现"这份变更建议是哪个版本、基于哪些事实给出的"。
- 工具白名单以套件 `tools.allow` 为准：`slow_log, explain, db_metrics, index_info, semantic_search, schema_link, analyze, ddl`；**无 `shell`**。
