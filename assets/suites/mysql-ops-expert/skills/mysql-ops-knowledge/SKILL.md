---
name: mysql-ops-knowledge
version: 1.0.0
description: Internal MySQL operations knowledge base — metric thresholds, symptom-to-root-cause decision trees, read-only diagnostic command library, and safety red lines. Referenced by other skills, not shown in the user menu.
name_en: MySQL Ops Knowledge Base
name_zh: MySQL 运维知识库
description_en: Internal MySQL operations knowledge base with thresholds, decision trees, commands, and safety rules.
description_zh: MySQL 运维内部知识库：指标阈值基准、现象→根因决策树、只读诊断命令清单与安全红线，供套件内其他技能引用。
user-invocable: false
---

# MySQL 运维知识库（内部）

本技能不直接面向用户，是套件内其他技能（SQL 体检 / 巡检 / 故障应急 / 变更评审 / 备份恢复 / 参数调优 / 运维报告）的**共享判定基准**。

被引用时的使用原则：**先读基准，再下结论**。任何"这个值正常吗 / 这个现象是什么原因"的判断，都必须能追溯到本知识库的某一节，避免凭印象给建议。

## 索引

| 文件 | 内容 | 什么时候读 |
|:---|:---|:---|
| [指标阈值基准](references/metrics-thresholds.md) | 连接数、QPS/TPS、锁等待、复制延迟、Buffer Pool、临时表、IO、磁盘、内存的绿/黄/红判据与取值来源 | 判断"这个指标算不算异常" |
| [现象→根因决策树](references/diagnostic-decision-tree.md) | 10 类故障现象的排查顺序、验证命令、止血动作、常见误区 | 定位问题、写 runbook、复盘归因 |
| [只读诊断命令清单](references/command-cheatsheet.md) | 按场景分组的安全 SQL 与 shell 命令，含 5.7/8.0 差异写法 | 需要告诉用户"跑什么命令拿数据" |
| [安全红线与执行分级](references/safe-execution-rules.md) | 命令分级、变更红线、数据脱敏、云上限制 | 输出任何可执行命令或建议前的强制自检 |

## 版本与形态差异（贯穿全库的默认约定）

- **默认假设**：MySQL 8.0 / InnoDB / SSD / 独立实例。若用户是 5.7，涉及 `performance_schema` 表结构、`information_schema.innodb_lock_waits`（8.0 移到 `data_locks`/`data_lock_waits`）、`EXPLAIN FORMAT=TREE`、降序索引/函数索引、`innodb_dedicated_server` 等，需显式给出 5.7 的替代写法。
- **云 RDS（阿里云 / 腾讯云 / AWS）**：多数无 OS 层权限，`SUPER`、`SET GLOBAL`、部分 `performance_schema` consumer 受限。诊断优先走控制台监控 + `SHOW` / I_S 视图；参数修改需在控制台参数模板里做，且区分**动态参数**与**需重启参数**。
- **主从 / 多副本**：巡检与诊断默认在**从库**执行重查询；但复制延迟、Follower 读旧数据类问题必须在主库与从库分别取数对比。
- **MariaDB / Percona**：MariaDB 无 `performance_schema` 同等能力（用 `sys` 库缺失时的替代 SQL 见命令清单）；Percona 额外可用 `pt-*` 工具集与 `INFORMATION_SCHEMA` 扩展表。

## 结论表达规范（所有技能共用）

输出任何诊断结论时，遵循三元结构：

1. **判定**：正常 / 需关注 / 需处理（红黄绿），并给出依据的具体数值。
2. **依据**：来自哪条指标、哪个视图、阈值基准的哪一条。
3. **动作**：立刻做什么（含具体命令）、观察多久、什么条件下升级处理。

禁止输出"建议优化一下"这类无锚点表述。数值缺失时明确写"待采集：`<命令>`"，不要用估计值填充。
