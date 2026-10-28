# PITR 与误删找回手册

命令中的路径/账号按实际替换。**每个阶段都有校验点，校验不过不得进入下一阶段。**

---

## 一、整库时间点恢复（PITR，标准链路）

### 阶段 0：确定恢复目标点

| 目标点依据 | 怎么定 |
|:---|:---|
| 业务给了时刻 | 直接取该时刻**之前** 5–30s 作为安全边界 |
| 只知道"误删之前" | 从 binlog 定位误删语句的 **起始位点**，恢复到该语句之前 |
| 有事务标识（订单号/批次） | `grep` binlog 反解内容找该事务的 GTID / `END_LOG_POS` |
| 崩溃恢复（主库损毁） | 恢复到候选从库应用的最后一个 GTID 集合 |

```sql
-- 8.0：定位精确位点（从库/临时实例上执行，L0）
SHOW BINLOG EVENTS IN 'binlog.000123' FROM 4 LIMIT 200;
```
```bash
# 反解出人可读的语句与时间戳，用来定边界
mysqlbinlog --no-defaults -vv --base64-output=decode-rows binlog.000123 \
  | grep -nE '^#[0-9]{14}|^SET TIMESTAMP|^### (DELETE|UPDATE|INSERT)' | head -100
```
**必须记录**：目标 `文件名:位点` 或 `GTID 集合`，写进恢复方案，事后作为审计依据。

### 阶段 1：准备隔离环境
- 新主机 / 新端口（如 `3307`）/ 云上新建实例。**禁止在生产数据目录操作。**
- 磁盘需求 ≥ `全备大小 × 2`（含 binlog 回放与临时空间）。
- 版本必须 **≥** 备份集版本；大版本不同不可用物理恢复（改走逻辑）。

### 阶段 2：恢复全备
```bash
# 校验备份集（必须输出 completed OK!）
xtrabackup --prepare --target-dir=/backup/full_20261027 2>&1 | tail -5
cat /backup/full_20261027/xtrabackup_binlog_info   # ← 记下这里的 binlog 文件与位点
cat /backup/full_20261027/xtrabackup_info | grep -E 'lsn|tool_version|binlog'

mv /var/lib/mysql /var/lib/mysql.orig            # 保留原件，勿删
mkdir -p /var/lib/mysql && chown -R mysql:mysql /var/lib/mysql
xtrabackup --copy-back --target-dir=/backup/full_20261027   # 大库慢，可加 --parallel
chown -R mysql:mysql /var/lib/mysql

mysqld --defaults-file=/etc/my.cnf --skip-networking=0 &     # 起来前先看错误日志
mysql -e "SELECT @@datadir, @@version; SHOW DATABASES;"
```
云快照恢复：控制台"恢复到新实例"，注意**新实例默认不可被生产访问**，仍需做后续 binlog 应用与校验。

### 阶段 3：应用 binlog 到目标点
```bash
# 3.1 从全备位点开始，取到目标点之前的所有 binlog
mysqlbinlog --no-defaults -R \
  --start-position=<全备记录的位点> --start-server=<源库> \
  binlog.000118 binlog.000119 binlog.000120 ... > /tmp/incr.sql
# 或用 GTID 更省心
mysqlbinlog --no-defaults --include-gtids='<gtid集合>' binlog.000118.. > /tmp/incr.sql

# 3.2 精确截断到目标点（三选一）
#   a) --stop-datetime='2026-10-27 10:30:45'
#   b) --stop-position=<误删语句起始位点>      ← 同一 binlog 文件内最精确
#   c) 先全导出，再用 sed/awk 手工裁到目标事务前 —— 大文件时更可控
mysqlbinlog --no-defaults --stop-position=58213 binlog.000123 >> /tmp/incr.sql

# 3.3 应用（恢复实例上执行）
mysql --port=3307 -e "SET sql_log_bin=0; SOURCE /tmp/incr.sql;"   # ⚠️ 见下
```
> `sql_log_bin=0` 是否关闭：**恢复实例若不需要再往下复制则关闭以免产生海量 binlog**；若恢复实例还要作为新主库搭复制，则必须保持开启并记录其 GTID 集合。这一步做错会导致后续切换时 GTID 冲突或链路断裂。
> 遇到 `ERROR 1062/1032` 等重复/找不到行错误 → **停手**，说明位点或备份链有偏差，回到阶段 0 重定位，不要用 `--force` 跳错误（跳一个错就可能引入不一致）。

### 阶段 4：校验
```sql
-- 目标对象层面
SELECT COUNT(*), MIN(id), MAX(id), SUM(amount) FROM <db>.<tbl>;
-- 与业务口径对账（关键）：故障前最后一个正确状态的合计值/订单数
-- 时间类抽查
SELECT MAX(gmt_modified) FROM <db>.<tbl>;      -- 应 ≤ 目标时间点
-- 结构
SELECT table_schema,COUNT(*) FROM information_schema.tables GROUP BY 1;
```
校验清单（逐项过）：行数、聚合值（金额/积分等可核对字段）、最后更新时间、主键连续性、GTID 集合、字符集/时区与生产一致（`@@time_zone`、`@@system_time_zone`、`character_set_database` — 时区错会让整段恢复数据"看起来不对"）。

### 阶段 5：切换
1. 停写原实例（或保持只读）并确认其最后一批事务已被回放/记录。
2. 恢复实例与生产实例做**增量对齐**：把"目标点之后到停写时刻"的正确数据按主键抽取回补（这是最容易丢数据的环节）。
3. 双向核对差异行；应用连接串切换；观察 ≥ 30 min。
4. 原实例保留 `mysql.orig` 与全部 binlog ≥ 7 天（用于二次核查）。

**不可逆点**：阶段 5 第 1 步（开始往生产写恢复数据）之后。之前所有步骤都可放弃重来。

---

## 二、误删找回：binlog 闪回（反向 SQL）

适用：`binlog_format=ROW` + `binlog_row_image=FULL` + 有覆盖删除时刻的 binlog。

### 方式 A：用工具（推荐）
```bash
# myflash（美团）/ binlog2sql（基于 python-mysql-replication）/ Row2Split 等
binlog2sql -h<h> -P3306 -u<binlog_user> -p<p> -d<db> -t<tbl> \
  --start-datetime='2026-10-27 10:30:00' --stop-datetime='2026-10-27 10:31:00' \
  -B -U --no-primary-keys=false > /tmp/rollback.sql     # -B = 生成回滚 SQL
# 人工审阅！确认只含目标表的 INSERT，且行数与预期一致
grep -c '^INSERT' /tmp/rollback.sql; head -20 /tmp/rollback.sql
```
> 闪回生成的是"删除前的镜像行"，因此**回写前必须确认目标行现在确实不存在**（若期间已被其他流程重新插入，直接 INSERT 会主键冲突；需改 `INSERT ... ON DUPLICATE KEY UPDATE` 或先按主键比对）。

### 方式 B：手工从 binlog 提取
```bash
mysqlbinlog --no-defaults -vv --base64-output=decode-rows \
  --database=<db> --start-datetime='...' --stop-datetime='...' \
  binlog.000123 | awk '/### DELETE FROM `<db>`\.`<tbl>`/{f=1} f&&/^### /{print} /^COMMIT/{f=0}' \
  > /tmp/deleted_rows.txt
```
把 `### WHERE @1='x' @2='y'` 转成 INSERT 时，**必须用 `SHOW CREATE TABLE` 的列顺序映射 `@N`**（`@1` 是表定义顺序的第 1 列，不是显示顺序）。列数错位是手工闪回最常见、最隐蔽的错误。

### 回写规范
```sql
-- 1) 先入影子表（L1）
CREATE TABLE <tbl>_recover_20261027 LIKE <tbl>;
LOAD DATA / 批量 INSERT 进影子表;
-- 2) 校验（L0）
SELECT COUNT(*) FROM <tbl>_recover_20261027;
SELECT COUNT(*) FROM <tbl> t JOIN <tbl>_recover_20261027 r USING(<pk>) WHERE 1=1; -- 冲突行
-- 3) 分批回写（L2）
INSERT INTO <tbl> (<cols>) SELECT <cols> FROM <tbl>_recover_20261027 r
 WHERE NOT EXISTS (SELECT 1 FROM <tbl> o WHERE o.<pk>=r.<pk>) ORDER BY r.<pk> LIMIT 2000;  -- 循环
-- 4) 保留影子表 ≥ 7 天后归档删除
```
> 回写会触发业务侧的 binlog 下游同步（数仓/搜索/缓存）——**必须提前通知**，否则下游收到一批"凭空出现"的历史数据。

---

## 三、延迟从库救场（若有）

```sql
SHOW REPLICA STATUS\G      -- 看 SOURCE_DELAY 与实际是否仍在延迟窗口内
-- 若从库尚未回放删除语句：立刻停止回放，把它变成"只读数据源"
STOP REPLICA;              -- [L1] 保住数据，不要 START
-- 从该从库抽缺失数据回写生产
```
⚠️ 抽数期间该从库不能恢复回放；恢复 `START REPLICA` 前确认位点/权限未被破坏。

## 四、延迟从库的建设（改进项标准答案）

```sql
CHANGE REPLICATION SOURCE TO SOURCE_DELAY=3600;   -- [L2] 1 小时延迟从库
START REPLICA;
```
说明代价：该从库数据永久落后 1h，**不可承载读流量**；用途是误删兜底。必须有告警区分"故意延迟"与"真故障延迟"，否则每次告警都要人回忆一遍。

## 五、恢复后必做的收尾

- [ ] 记录：本次实际耗时（→ 更新 RTO 口径）、丢失数据量（→ 与业务确认的 RPO 对照）
- [ ] 恢复实例/影子表/全部 binlog 保留 ≥ 7 天，再按流程归档
- [ ] 检查配置是否残留（`read_only`、`sql_log_bin`、复制参数、临时放开的权限）
- [ ] 监控项补齐：备份成功率、binlog 连续性、备份大小突变、恢复演练到期提醒
- [ ] 复盘改进项按 @故障应急 模板登记到任务系统
