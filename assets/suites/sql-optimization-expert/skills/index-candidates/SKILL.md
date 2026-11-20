---
name: index-candidates
name_zh: 索引候选评估
name_en: Index Candidates
description: Recommend index candidates from supplied queries and existing indexes. Use for index advice or redundancy review. Do not create indexes or promise measured gains.
description_zh: 用户要求索引推荐、联合索引设计或冗余索引评估时使用；输出候选 DDL、适用条件、写入代价与实测方案。
command: /index-advise
argument-hint-zh: 提供目标表、常用 SQL 和已知读写负载
argument-hint-en: Supply target tables, common queries and read/write workload
user-invocable: true
---

# 索引候选评估

遵守[生产读取规则](../../references/production-readonly.md)，核对[结构与索引证据](../../references/database-evidence.md)。

1. 收集目标查询、已有索引定义、约束、谓词、排序和 JOIN 条件。缺少整体负载时限定建议只适用于已提供查询。
2. 比较已有索引与候选的列顺序、前缀、覆盖范围、唯一性、部分/表达式索引及方言支持。前缀相同不自动意味着可以删除旧索引。
3. 将选择性未知、参数分布未知和统计缺失列为验证项；不执行大表 DISTINCT/COUNT 来猜测选择性。
4. 给出候选 DDL 文本，列出读取收益假设、写入维护成本、空间影响的依据及建索引锁/在线能力待确认项。
5. 交付候选清单、可复制 DDL、保留/合并理由与测试方案。未经实测不写“提升 X%”，不执行 CREATE/DROP INDEX。综合报告使用[报告模板](../../templates/optimization-report.md)。
