---
name: modeling-review
name_zh: 数据建模评审
name_en: Modeling Review
description: Review schema design against supplied business requirements. Use for entity modeling or schema evolution proposals. Do not apply DDL or assume missing business rules.
description_zh: 用户要求建模、表设计评审或架构改进时使用；输出证据、候选结构、取舍及兼容性验证，不实施变更。
command: /model-review
argument-hint-zh: 提供业务需求、目标表和主要访问模式
argument-hint-en: Supply business requirements, tables and access patterns
user-invocable: true
---

# 数据建模评审

遵守[读取边界](../../references/metadata-boundaries.md)，使用[模型评审清单](../../references/model-review.md)和[报告模板](../../templates/schema-report.md)。

1. 获取实体粒度、核心查询、读写特征与保留要求；缺少这些资料时限定为物理结构评审。
2. 检查键、关系、类型、NULL、时间与金额表示、约束、索引和演进兼容性，每条问题标证据。
3. 给候选模型、DDL 文本与取舍，区分现状和建议。没有业务资料时不自动认定反范式、软删除或未建 FK 是错误。
4. 输出应用兼容、数据回填、约束验证、灰度和数据恢复步骤；未知规模时不给迁移耗时估计。
5. 交付模型评审清单、可复制草案、待确认问题；完整报告调用 generate_report。禁止 DDL、业务数据写入与自动发布语义定义。
