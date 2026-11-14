# 数据字典交付契约

一行对应一个物理列，按 schema、table、ordinal_position 排序。

| 列 | 含义 |
| --- | --- |
| schema_name | 所属 schema 或数据库 |
| table_name | 物理表名 |
| column_name | 物理列名 |
| ordinal_position | 原始列序号 |
| data_type | 完整类型；可获得时包含长度、精度 |
| is_nullable | YES / NO / 未知 |
| column_default | 原始默认值；无默认与无法获取须区分 |
| is_primary_key | 已声明主键成员；无法查证时未知 |
| foreign_key_reference | 声明的引用对象和列；复合键映射保持正确 |
| column_comment | 原始注释；没有则未提供 |
| source | 真实目录或 DDL 来源 |

对话中展示少量列作为预览，并引用实际 CSV。完整覆盖与采集时点在报告说明。业务定义与推断解释放入单独确认表，不能替换原始字段注释。

CSV 使用 sql_query 返回的未截断 artifact_id 调用 export_csv；只允许导出真实查询结果。目录查询失败时交付 Markdown 字典并标明范围，不捏造 CSV 链接。
