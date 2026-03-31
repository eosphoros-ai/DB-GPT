# DB-GPT 集成总览

DB-GPT 支持多种数据源、RAG 存储以及图谱存储集成，帮助你把数据库、数仓、知识库和检索系统快速接入到 DB-GPT 中。

## 数据源提供方

| 提供方 | 是否支持 | 安装参数 |
|---|---|---|
| MySQL | ✅ | `--extra datasource_mysql` |
| OceanBase | ✅ |  |
| ClickHouse | ✅ | `--extra datasource_clickhouse` |
| Hive | ✅ | `--extra datasource_hive` |
| MSSQL | ✅ | `--extra datasource_mssql` |
| PostgreSQL | ✅ | `--extra datasource_postgres` |
| Apache Doris | ✅ |  |
| StarRocks | ✅ |  |
| Spark | ✅ | `--extra datasource_spark` |
| Oracle | ✅ | `--extra datasource_oracle` |
| GaussDB | ✅ | `--extra datasource_postgres` |
| openGauss | ✅ | `--extra datasource_postgres` |

## RAG 存储提供方

| 提供方 | 是否支持 | 安装参数 |
|---|---|---|
| Chroma | ✅ | `--extra storage_chroma` |
| Milvus | ✅ | `--extra storage_milvus` |
| Elasticsearch | ✅ | `--extra storage_elasticsearch` |
| OceanBase | ✅ | `--extra storage_obvector` |

## Graph RAG 存储提供方

| 提供方 | 是否支持 | 安装参数 |
|---|---|---|
| TuGraph | ✅ | `--extra graph_rag` |
| Neo4j | ❌ |  |

## 下一步

如果你关注的是结构化数据接入，可以继续阅读各个数据源安装文档，例如：

- ClickHouse
- PostgreSQL
- DuckDB
- MSSQL
- Oracle
- MySQL
- SQLite
- OceanBase
- GaussDB
- Apache Doris
- StarRocks
- Vertica

如果你关注的是检索增强生成（RAG）能力，可以继续阅读对应的向量存储和图谱存储集成文档。
