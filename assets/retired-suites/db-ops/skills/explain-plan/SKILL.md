---
name: explain-plan
name_zh: 执行计划解读
name_en: Execution Plan Review
description_en: Interpret a SQL execution plan and identify full scans, index issues, sorting, and lock evidence. Clearly mark findings that still require verification.
argument-hint-en: Review the EXPLAIN output for this SQL and identify plan issues
command: /explain
description: 解读单条 SQL 的执行计划，定位全表扫描、索引失效、排序与锁等待证据。
user-invocable: true
argument-hint-zh: 对以下 SQL 做 EXPLAIN 判读并指出坏计划原因：
---

# 执行计划解读

遵循[慢查询诊断技能](../slow-query-diagnosis/SKILL.md)与其中的根因及安全参考。
优先解读用户给出的 SQL 与 EXPLAIN；已连接目标库且获准时才能采集。
没有真实执行计划时明确标注待验证，不虚构 rows、耗时或索引命中。
修复动作只出提案，不自动执行 DDL 或 ANALYZE。
