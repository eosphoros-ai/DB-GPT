# SQL 优化专家

面向直连数据库的只读诊断与方案交付套件，支持 DB-GPT 和 PI 的现有工具链。版本 1.0.0。

## 使用

在“专家套件”中选择 SQL 优化专家，绑定已授权的数据源并提供 SQL 或 DDL。

| 命令 | 交付 |
| --- | --- |
| /sql-diagnose | 诊断结论、普通执行计划证据、完整任务的 HTML 报告 |
| /sql-rewrite | 可复制 SQL、修改对照、语义等价验证清单 |
| /index-advise | 索引候选 DDL、已有索引对比、成本与实测方案 |
| /sql-review | 变更风险、前置条件、上线验证与回退清单 |

HTML 报告由 generate_report 返回真实预览/下载产物；SQL 和 DDL 默认以代码块交付，也收录进报告。export_csv 仅导出已经执行且未截断的证据查询结果，不生成 SQL 草案文件。

## 能力与边界

初版优先 MySQL、PostgreSQL、SQLite。其他方言依据用户提供的 DDL 和计划做静态评审。没有实时计划或代表性参数时，不能证明真实性能收益或 SQL 等价。

只允许 sql_query、export_csv 和 generate_report，不开放 shell、代码执行或变更工具。账号权限、数据库端超时、连接预算与查询成本控制需部署侧配置；本套件不代表完整生产安全改造。

详见[工作规程](prompts/workflow.md)、[生产读取规则](references/production-readonly.md)和[报告模板](templates/optimization-report.md)。
