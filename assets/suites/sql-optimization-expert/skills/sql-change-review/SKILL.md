---
name: sql-change-review
name_zh: SQL 与 DDL 变更评审
name_en: SQL Change Review
description: Review supplied SQL or DDL as text for compatibility and rollout risk. Use before database changes. Do not execute DDL, writes or destructive validation.
description_zh: 用户要求 SQL、索引或 DDL 上线评审时使用；输出风险、前置条件、验证与回退方案，全程不执行变更。
command: /sql-review
argument-hint-zh: 提供变更脚本、数据库版本与上线约束
argument-hint-en: Supply the change script, database version and rollout constraints
user-invocable: true
---

# SQL 与 DDL 变更评审

遵守[生产读取规则](../../references/production-readonly.md)，使用[报告模板](../../templates/optimization-report.md)。

1. 将用户脚本作为文本审查；禁止为确认语法直接执行 DDL、DML 或 EXPLAIN 写入语句。
2. 获取明确的数据库版本、相关结构、依赖证据与业务约束。未知版本或数据量时，不确定在线 DDL 能力、锁时长或完成时间。
3. 检查数据丢失、类型收窄、NULL/默认值、唯一约束、索引维护、隐式提交、事务边界和应用兼容性。跨应用影响需代码/调用方资料，缺失时明确覆盖范围。
4. 提供备份与恢复条件、测试环境验证、灰度、监控观察和中止条件；区分可逆结构修改与需要数据恢复的破坏性变更。
5. 交付“建议通过 / 补充证据后再评审 / 当前不建议实施”的建议、逐项证据和上线清单；这不是审批结果，不能宣称生产已上线。
