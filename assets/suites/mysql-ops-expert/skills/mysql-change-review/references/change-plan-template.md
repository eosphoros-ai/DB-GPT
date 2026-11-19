# 变更方案模板

文件名：`outputs/change-plan-<对象>-<YYYYMMDD>.md`。
标注 **[必填]** 的项缺失即评审不通过。

---

# 变更方案：<一句话描述>

| 项 | 值 |
|:---|:---|
| 变更单号 | `<...>` **[必填]** |
| 关联需求/故障 | `<需求单 / 巡检问题编号 P1-x / 故障复盘改进项 A1>` |
| 目标实例 | `<实例>`（角色：主 / 从；MySQL `8.0.x`；拓扑：1 主 N 从） |
| 变更对象 | `<db>.<tbl>` — **`N` 行 / 数据 `X` GB / 索引 `Y` GB** **[必填]** |
| 变更内容 | `<DDL / 订正 / 参数>` **[必填]** |
| 执行方式 | `ALGORITHM=INSTANT` / `INPLACE,LOCK=NONE` / `COPY` / `gh-ost` / `pt-osc` / 分批 DML **[必填]** |
| 风险等级 | 🟢L1 / 🟡L2 / 🔴L3 |
| 申请窗口 | `2026-10-28 02:00–04:00`（业务低谷；已确认无备份/批处理/结算任务冲突） |
| 执行人 / 复核人 / 值班 | `<姓名>` / `<姓名>` / `<姓名>` |
| 是否需停写 | 否 / 是（停写时长 `<m>` min，流量摘除方式 `<...>`） |

## 1. 变更动机与收益 [必填]

**为什么做**：`<来自哪条巡检结论/故障复盘改进项，含实测数值>`
**做完的验收口径**：`<如：目标 SQL 扫描放大比从 3100 降到 <10，p95 从 8.2s 降到 <200ms>`
**不做的代价**：`<...>`

## 2. 影响面分析 [必填]

| 维度 | 评估 | 依据 |
|:---|:---|:---|
| 锁影响 | DML 全程可写；**开始/结束瞬间各需一次 MDL 写锁（<1s）** | 执行方式 |
| 预计耗时 | 主库 `<min>`（估算：`<字节> ÷ <吞吐 MB/s> × 冗余系数 1.5`） | 见工具选型 §耗时估算 |
| 空间峰值 | +`<GB>`（影子表/临时空间）；变更后净增 `<GB>` | 当前磁盘余量 `<GB>`（**是否 > 峰值 2 倍：是/否**） |
| 从库延迟 | 预计 `<min>`（≈ 主库执行耗时 + 行事件回放） | 当前延迟 `<s>` |
| binlog 产出 | 约 `<GB>`（RBR + `binlog_row_image=FULL`） | 表大小 |
| 下游链路 | DTS/Canal `<任务名>` 位点预计滞后 `<min>`；已通知 `<人>` | 订阅关系清单 |
| 受影响 SQL | `<digest 前 8 位列表>`，其中 `<n>` 条执行计划会变 | 慢日志/digest |
| 应用兼容 | 新代码可读旧结构 ✓ / 旧代码可读新结构 ✓（双向兼容 = 可回滚前提） | 代码检查 |

## 3. 前置检查（逐条执行并留存输出）[必填]

```sql
-- [L0] 3.1 对象规模与磁盘余量
SELECT table_rows, ROUND((data_length+index_length)/1024/1024/1024,2) gb
FROM information_schema.tables WHERE table_schema='<db>' AND table_name='<tbl>';
SELECT table_name,index_name FROM information_schema.statistics
WHERE table_schema='<db>' AND table_name='<tbl>' GROUP BY 1,2;   -- 确认索引不重复

-- [L0] 3.2 无长事务/长查询（MDL 阻塞源）
SELECT trx_mysql_thread_id thd, trx_started,
       TIMESTAMPDIFF(SECOND,trx_started,NOW()) sec, trx_rows_modified
FROM information_schema.innodb_trx
WHERE trx_started < NOW() - INTERVAL 30 SECOND;
SELECT id,time,state,LEFT(info,80) q FROM information_schema.processlist
WHERE command='Query' AND time>30;
-- 判停标准：存在 > 30s 事务或查询 → 先处理，否则不开工

-- [L0] 3.3 复制健康
SHOW REPLICA STATUS\G      -- Seconds_Behind_Source < 10 且双线程 Yes 才开工

-- [L0] 3.4 参数与算法支持
SELECT @@innodb_online_alter_log_max_size, @@binlog_format, @@binlog_row_image, @@version;

-- [L0] 3.5 备份可用性（删除/订正类必查）
-- 最近全备时间：<...>；binlog 覆盖：<起点>–<终点>；恢复演练：是/否
```

- [ ] 已确认目标表近 7 天无其他变更计划（避免并发变更互相阻塞）
- [ ] 已在从库/影子表演练一次，记录耗时 `<min>`（**大表必做**）
- [ ] 应急联系人就位：`<DBA>` `<业务 owner>` `<平台/云工单号>`

## 4. 执行步骤 [必填]

| # | 时间预算 | 操作（含完整命令） | 观测点 | 判停标准 → 动作 | 级别 |
|:--|:--|:--|:--|:--|:--|
| 1 | 2 min | `SET SESSION lock_wait_timeout=10;` | — | — | L1 |
| 2 | 1 min | 创建 throttle 文件 / 打开应用降级开关 | 错误率 | 错误率 > 基线 → 终止 | L1 |
| 3 | 45 min | `ALTER TABLE <db>.<tbl> ADD INDEX idx_x (a,b), ALGORITHM=INPLACE, LOCK=NONE;` 或 gh-ost 命令 | gh-ost 进度 / processlist State / `Seconds_Behind_Source` | 延迟 > 60s 或 `Threads_running` > 核数×3 → 暂停（throttle 置位）或 `KILL` 该 DDL | L2 |
| 4 | 3 min | `EXPLAIN FORMAT=TREE <目标SQL>;` 验证新计划 | `key`/`key_len`/`rows` | 计划未变 → 回滚并复盘 | L0 |
| 5 | 2 min | 清理 throttle、恢复降级开关 | 业务指标 | — | L1 |

**每个步骤必须可中断**；步骤 3 是唯一长耗时步骤，其"跑到一半很慢怎么办"见 [工具选型 §中止](online-ddl-tooling.md)。

## 5. 回滚方案 [必填 — 缺失即一票否决]

```sql
-- 情况 A：变更成功但效果不符预期
ALTER TABLE <db>.<tbl> DROP INDEX idx_x, ALGORITHM=INPLACE, LOCK=NONE;   -- 预计 <2 min>

-- 情况 B：执行中断/失败
-- INPLACE：KILL 会话后 InnoDB 自动回滚，确认无残留
SELECT table_name FROM information_schema.tables
 WHERE table_name LIKE '#sql-%' OR table_name LIKE '%_gho' OR table_name LIKE '%_ghc' OR table_name LIKE '%_old';
-- gh-ost：直接删除 <tbl>_gho / <tbl>_ghc 影子表（安全，主表未被切换）
-- pt-osc：确认触发器与影子表状态后再清理，勿盲目 DROP
```
**不可逆性说明**：`<本变更完全可逆 / 部分可逆（列出不可逆步骤与补偿）>`
**回滚耗时**：`<min>`；**回滚决策人**：`<姓名>`；**回滚触发条件**：`<明确阈值 + 观察时长>`

## 6. 变更后验证 [必填]

- [ ] 结构：`SHOW CREATE TABLE <tbl>\G` 与预期一致
- [ ] 计划：目标 SQL `EXPLAIN ANALYZE` 实测在预期区间（`<X>` ms）
- [ ] 指标：`Threads_running`、CPU、慢查询数回落到基线（观察 ≥ 15 min）
- [ ] 复制：`Seconds_Behind_Source` 归零；GTID 主从集合一致
- [ ] 下游：DTS/Canal 任务无报错、位点追上
- [ ] 其他 SQL 无计划劣化：`<受影响 digest 列表>` 逐条 `EXPLAIN` 复核
- [ ] 业务：错误率、核心成功率符合基线
- [ ] **临时措施已回退**：`<列出本次为变更放宽的参数/开关及回退命令>`

## 7. 遗留与后续

- `<如：旧索引 idx_y 观察一个完整业务周期后再下线，已建待办 #…>`
- `<如：本表 2027 Q1 预计达 8000 万行，归档方案另行评审>`

## 8. 评审结论

| 项 | 结果 |
|:---|:---|
| 结论 | ✅ 通过 / ⚠️ 有条件通过 / ❌ 不通过 |
| 条件（若有） | `<如：需先补 3.5 的恢复演练证据；需将窗口移至备份之后>` |
| 未覆盖风险 | `<列表>` |
| 评审时间 | `2026-10-27` |

> 本方案基于 `<数据来源与采集时间>`。执行前请人工复核第 3 节全部前置检查，L2/L3 操作需二次确认。
