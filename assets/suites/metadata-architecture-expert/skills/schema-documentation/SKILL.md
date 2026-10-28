---
name: schema-documentation
name_zh: 数据库结构文档
name_en: Schema Documentation
description: Produce traceable schema documentation with dictionary and relationships. Use for database handover or architecture reports. Do not claim full coverage from partial metadata.
description_zh: 用户要求数据库说明、交接文档或结构报告时使用；综合字典、真实关系与来源，生成 HTML 文档。
command: /schema-doc
argument-hint-zh: 指定数据库文档范围和目标读者
argument-hint-en: Specify documentation scope and audience
user-invocable: true
---

# 数据库结构文档

遵守[读取边界](../../references/metadata-boundaries.md)和[方言采集策略](../../references/catalog-sources.md)，采用[结构报告模板](../../templates/schema-report.md)。

1. 明确读者、schema、表范围与数据时点；分批采集时记录已覆盖、未覆盖和无权限对象。
2. 汇总物理列、约束、索引与注释；可选采用已发布语义定义，禁止草稿当作正式口径。
3. 交付数据字典、物理关系、设计特点与缺失知识。任何实体用途推断标为待确认。
4. 先完成证据整理，再调用 generate_report；复用 query artifact_id，将上下文结构的实际来源传入报告。必要时导出真实字典 CSV。
5. 只有报告 completed 且返回真实产物才宣布文件完成。最终给摘要、HTML/CSV 链接与需要确认的事项；没有文件则提供 Markdown 版本并明确原因。
