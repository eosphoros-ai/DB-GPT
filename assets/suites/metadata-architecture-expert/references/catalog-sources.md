# 方言采集策略

使用真实方言与明确范围构造只读目录 SELECT。不得以未执行的例子充当证据。

| 方言 | 表列 | 主键、外键、索引与注释 |
| --- | --- | --- |
| MySQL | information_schema.tables、columns，过滤 table_schema/table_name | table_constraints、key_column_usage、referential_constraints、statistics；列注释来自 columns |
| PostgreSQL | information_schema.columns 与 pg_catalog，明确 namespace | pg_constraint、pg_attribute、pg_index、pg_indexes、pg_description；复合 FK 按 conkey/confkey 序号对应，不与其他 schema 同名对象混淆 |
| SQLite | sqlite_master 与 SELECT 查询的 pragma_table_info 表值函数 | pragma_foreign_key_list、pragma_index_list、pragma_index_info；SQLite 没有通用原生列注释，不编造 |
| 其他 | 已验证目录或用户提供 DDL | 限定可证明的物理结构，注明未适配项 |

sql_query 不接受直接 SHOW/PRAGMA，使用受支持的 SELECT/WITH。表值 PRAGMA 函数是否可用取决于 SQLite 版本，失败时可根据 sqlite_master 的真实 DDL 整理文档，但不能假装已导出完整字段 CSV。

为数据字典构造一条限定范围的目录 SELECT，投影为：
schema_name、table_name、column_name、ordinal_position、data_type、is_nullable、column_default、is_primary_key、foreign_key_reference、column_comment、source。

主键和外键信息用按列聚合的子查询后再 JOIN，避免一列多个约束将字典行数放大。无法查询约束时填“未知”，而不是 false。CSV 保留物理元数据；推断业务解释留在报告，不能冒充目录原值。

导出前检查 query 产物是否 truncated，缺失或截断时停止完整导出承诺。查询有 LIMIT 时记录页范围；未取得全库清单时不声称所有对象已覆盖。

semantic_get_metadata 的 limit 为 1–50，返回快照而非实时全库目录，不能把单次响应称为全量。semantic_search_business 无已发布结果时，只表示语义缺失。
