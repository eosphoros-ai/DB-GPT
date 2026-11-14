---
name: physical-er
name_zh: 物理 ER 图
name_en: Physical ER
description: Build physical ER diagrams from declared keys and foreign keys. Use for schema relationships or ER documentation. Do not present inferred joins as lineage.
description_zh: 用户要求 ER 图、表关系或物理架构图时使用；真实约束与候选推断分开，交付可渲染图与 draw.io、DBML、Mermaid、SVG 下载文件。
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
4. 必须调用 generate_er_diagram，不以 Markdown 代码块代替渲染产物。model 参数包含 title、evidence_artifact_ids（本会话 sql_query 返回的真实且未截断的元数据查询 ID）、tables（id/name/schema/columns，列含 name/type/primary_key/nullable）和 relationships（name/from_table/to_table/from_columns/to_columns/kind/basis）。kind 只能是 declared 或 inferred，每条关系给出来源依据，复合键按列对应。没有 FK 时仍生成表字段图，relationships 可以为空。
5. 检查工具返回 success；交付内联可缩放 HTML 图、drawio（diagrams.net 打开编辑）、DBML（dbdiagram 导入）、Mermaid 源码、SVG 和 JSON。推断关系在渲染图和 draw.io 中为虚线，在 DBML 中仅作注释，不转换为真实约束。Mermaid 使用安全别名；基数未确认时不得宣称已经证明一对多。下载采用工具实际产物，不编造链接。
6. 大范围按业务域拆分，每图不超过 60 表、每表 150 列、200 条关系；说明图中字段范围，保留完整关系映射与证据。完整报告可再调用 generate_report，引用已生成图及关系表。工具失败时说明原因，交付关系表和源码，不宣称已生成可下载图。
