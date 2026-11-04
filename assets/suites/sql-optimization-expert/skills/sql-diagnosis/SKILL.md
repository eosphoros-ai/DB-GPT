---
name: sql-diagnosis
name_zh: SQL 性能诊断
name_en: SQL Diagnosis
description: Diagnose a supplied SQL using schema, indexes and plain EXPLAIN. Use for slow query analysis or an optimization report. Do not execute business queries or changes.
description_zh: 用户提供 SQL 或执行计划并要求性能诊断、慢查询分析或优化报告时使用；默认只读，区分静态判断与计划证据。
command: /sql-diagnose
argument-hint-zh: 提供 SQL、目标表和已知慢查询现象
argument-hint-en: Supply SQL, target tables and the observed performance issue
user-invocable: true
---

# SQL 性能诊断

遵守[生产读取规则](../../references/production-readonly.md)，使用[数据库证据采集](../../references/database-evidence.md)。

1. 识别目标 SQL、方言、参数与症状，收集相关表和现有索引，不做无范围全库巡检。
2. 对只读 SQL 获取普通 EXPLAIN；用户已有计划时先解读，不重复执行。无法取计划时只做静态诊断。
3. 检查扫描方式、谓词可索引性、JOIN 顺序与基数、排序/临时处理、估计行数和索引使用。把每条结论对应到证据，不把扫描方式本身判成故障。
4. 按收益假设与验证成本排序，给出少量可落实的候选方案；索引收益和耗时改进不量化为未经验证的数字。
5. 完整诊断按[报告模板](../../templates/optimization-report.md)调用 generate_report。交付对话结论、HTML 报告真实链接和验证步骤；无法生成文件时明确降级。
