---
name: physical-er
name_zh: 物理 ER 图
name_en: Physical ER
description: Build physical ER diagrams from declared keys and foreign keys. Use for schema relationships or ER documentation. Do not present inferred joins as lineage.
description_zh: 用户要求 ER 图、表关系或物理架构图时使用；真实约束与候选推断分开，交付关系表和 Mermaid 源码。
command: /physical-er
argument-hint-zh: 指定要展示关系的表或 schema
argument-hint-en: Specify tables or schema for the relationship diagram
user-invocable: true
---

# 物理 ER 图

遵守[读取边界](../../references/metadata-boundaries.md)，使用[目录证据](../../references/catalog-sources.md)与[报告模板](../../templates/schema-report.md)。

1. 收集主键、唯一键、外键列对应及 nullable，确保跨 schema 和复合键映射准确。
2. 将声明外键放入真实关系表，按约束表达实体连接。基数需结合唯一性和 NULL；无法证明的部分明确为推断条件。
3. 名称相似、用户建议 JOIN 或缺少约束的关联，放入独立候选表。没有 FK 时输出“未发现可见声明外键”，不补造真实图边。
4. 输出 Mermaid erDiagram 代码块。对标识符做安全别名映射，原始全限定名保留在关系表；不让字段注释破坏图语法。
5. 大范围图按业务域拆分，图中优先主外键字段。交付源码、关系表与范围；完整报告请求 generate_report 静态呈现图，无法渲染时明确保留源码与关系表。
