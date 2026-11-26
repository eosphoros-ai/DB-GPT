# 数据库证据采集

优先用会话内的方言、表结构和现有索引信息。以下是生成采集 SQL 的策略，不是已经执行的记录。使用明确的目标对象和真实字段，查询失败时不要假设系统目录已经存在。

| 方言 | 普通计划 | 结构与索引来源 |
| --- | --- | --- |
| MySQL | EXPLAIN SELECT …；仅在兼容性明确时使用 FORMAT=JSON | information_schema.columns、statistics、table_constraints、key_column_usage；同时限制 table_schema 和 table_name |
| PostgreSQL | EXPLAIN SELECT … | pg_catalog 与 information_schema；pg_indexes 可获取索引定义，目录 OID 与 schema 必须对应目标对象 |
| SQLite | EXPLAIN QUERY PLAN SELECT … | sqlite_master，以及可用的 pragma_table_info、pragma_index_list、pragma_index_info 表值函数 |
| 其他 | 用户提供的计划或经核实的方言命令 | 用户提供 DDL/索引；不套用 MySQL 系统表 |

sql_query 接受只读 SELECT/WITH 及受支持的 EXPLAIN，不支持直接 SHOW/PRAGMA。不要依赖未接入的 db_explain、db_metrics 或 shell 工具。PostgreSQL 的括号式 EXPLAIN 选项可能不被当前校验器接受，优先普通 EXPLAIN。

参数化 SQL 不应擅自填入敏感值。无法取得代表性参数时使用用户提供计划，或注明计划不代表具体参数分布。

执行计划记录 artifact_id、数据源、方言、采集时点和参数条件。schema 只来自会话上下文时，明确标注上下文来源和未知时点，不编造查询 artifact_id。

索引唯一性、主键与外键均以数据库目录或提供的 DDL 为证；名称相似不能证明约束存在。计划里的行数与成本属于估计，真实耗时只能来自已提供的实测数据。
