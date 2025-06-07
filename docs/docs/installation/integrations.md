# DB-GPT Integrations

DB-GPT integrates with many datasources and rag storage providers.

Integration Packages



# Datasource Providers

| Provider    | Supported | Install Packages     |
|-------------|-----------|----------------------|
| MySQL       | ✅       | --extra datasource_mysql |
| OceanBase   | ✅       |  |
| ClickHouse  | ✅       | --extra datasource_clickhouse |
| Hive        | ✅       | --extra datasource_hive |
| MSSQL       | ✅       | --extra datasource_mssql |
| PostgreSQL  | ✅       | --extra datasource_postgres |
| ApacheDoris | ✅       |                      |
| StarRocks   | ✅       | --extra datasource_starroks |
| Spark       | ✅       | --extra datasource_spark |
| Oracle      | ✅       | --extra datasource_oracle |


# RAG Storage Providers

| Provider    | Supported | Install Packages               |
|-------------|-----------|--------------------------------|
| Chroma      | ✅         | --extra storage_chroma         |       
| Milvus      | ✅         | --extra storage_milvus         |       
| Elasticsearch | ✅         | --extra storage_elasticsearch   |        
| OceanBase   | ✅         | --extra storage_obvector      |


# Graph RAG Storage Providers

| Provider | Supported | Install Packages |
|----------|-----------|------------------|
| TuGraph  | ✅         | --extra graph_rag|
| Neo4j    | ❌         |                  |
