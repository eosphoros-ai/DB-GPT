# 数据源

DB-GPT 的数据源模块用于管理企业中的结构化和半结构化数据资产，把数据库、数仓、数据湖等系统接入到 DB-GPT 框架中，从而快速构建面向数据场景的智能应用和大模型能力。目前 DB-GPT 已支持多种常见数据源，也支持自定义扩展。

<p align="center">
  <img src={'/img/app/datasource.jpg'} width="800px" />
</p>


你可以通过页面右上角的 **Add a data source** 按钮新增数据源。在弹出的对话框中，选择对应的数据库类型并填写所需参数后即可完成添加。

## 支持的数据源类型

当前 DB-GPT 文档已覆盖或正在补充以下数据源集成：

- MySQL
- SQLite
- ClickHouse
- PostgreSQL
- DuckDB
- Hive
- MSSQL
- Oracle
- OceanBase
- GaussDB
- openGauss
- Apache Doris
- StarRocks
- Vertica

## 数据源在 DB-GPT 中的作用

接入数据源之后，DB-GPT 可以基于这些结构化数据能力支持：

- 自然语言问数
- Text-to-SQL
- SQL 分析与执行
- 数据分析报告生成
- 与 agent、skill、工具链路联动的自动化分析

## 下一步

如果你想了解具体数据库的安装和接入方法，请继续阅读各个数据源集成页面。

如果你想了解 agent 如何结合数据库工作，可以继续阅读数据库与 agent 相关文档。

<p align="center">
  <img src={'/img/app/datasource_add.jpg'} width="800px" />
</p>
