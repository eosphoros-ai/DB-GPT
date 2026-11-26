---
name: sql-rewrite
name_zh: SQL 查询改写
name_en: SQL Rewrite
description: Propose dialect-correct SQL rewrites with semantic checks. Use when asked to rewrite or simplify a supplied query. Do not claim equivalence without verification.
description_zh: 用户要求优化写法、简化查询或改写 SQL 时使用；交付候选 SQL、变更说明和语义等价验证清单。
command: /sql-rewrite
argument-hint-zh: 粘贴原始 SQL，并说明必须保持的业务口径
argument-hint-en: Paste the original SQL and semantics that must be preserved
user-invocable: true
---

# SQL 查询改写

遵守[生产读取规则](../../references/production-readonly.md)。

1. 确认目标方言、表结构、唯一性与业务口径。保留原始 SQL，优先做最小改写。
2. 明确每处修改的目的及条件。检查 NULL 三值逻辑、NOT IN、外连接过滤、重复行、聚合粒度、时区与时间边界、排序和分页稳定性。
3. 不凭字段名假设唯一键，不擅自改动筛选条件、金额精度、时区或指标公式。证据不足时交付带条件的候选。
4. 可对原始和候选只读 SQL 获取普通计划，不执行查询结果对比。验证清单覆盖结果多重集、边界样例、代表性参数和执行性能。
5. 交付原始/候选 SQL 代码块、修改对照表、语义条件与待验证项。用户要求报告时按[报告模板](../../templates/optimization-report.md)生成 HTML；不得伪造 .sql 文件下载链接。
