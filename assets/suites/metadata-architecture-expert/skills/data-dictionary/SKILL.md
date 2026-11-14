---
name: data-dictionary
name_zh: 数据字典生成
name_en: Data Dictionary
description: Build a physical data dictionary from authorized metadata. Use for field documentation or dictionary CSV export. Do not invent business definitions or scan business rows.
description_zh: 用户要求字段说明、数据字典或字典 CSV 时使用；保留物理元数据与来源，业务含义缺失时列为待确认。
command: /data-dictionary
argument-hint-zh: 指定 schema 和目标表；不指定时先确认范围
argument-hint-en: Specify schema and target tables
user-invocable: true
---

# 数据字典生成

遵守[读取边界](../../references/metadata-boundaries.md)和[方言策略](../../references/catalog-sources.md)，按[字典契约](../../templates/data-dictionary.md)交付。

1. 确认表范围，读取目录并保留原始列序、类型、nullable、默认、主外键与注释。
2. 保证每个物理列一行，多约束先聚合；无权限查证约束时标未知，不标不存在。
3. 对缺失注释不猜测业务含义；可选查询已发布业务定义，放入报告并注明发布来源。
4. 用真实未截断 query artifact_id 调用 export_csv，给出数据字典 CSV 的真实文件链接。分批时提供各批范围；截断时重新缩小元数据范围，不能声称完整。
5. 最终交付范围、少量预览、CSV 与语义确认清单。用户需要完整文档时按[结构报告模板](../../templates/schema-report.md)生成 HTML。
