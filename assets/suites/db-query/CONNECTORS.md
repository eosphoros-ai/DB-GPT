# Connectors

本套件（`db-query`）以 DB-GPT 内置能力为核心执行链路，**不强依赖任何外部 MCP 连接器**即可运行。以下品类为**可选增强**，连上后自动化程度更高、审计更完整。

## 品类映射表

| 品类 | 连上后能做什么 | 候选工具 | 配置方式 |
|------|---------------|---------|---------|
| **语义层** | 双路召回（向量 + 精确匹配）、按 id 回源加载权威指标定义、样例库读写、规则护栏 | DB-GPT Semantic Layer（内置，`mysql_prod` 等语义空间） | 内置能力，无需 MCP；在 DB-GPT 语义中心页激活对应语义空间即可 |
| **数据源** | 只读从库路由、SQL 执行、结果集拉取、成本预估 | DB-GPT Datasources（内置连接器管理） | 内置能力，在数据源页配置连接（MySQL / PostgreSQL / SQLServer / DuckDB 等） |
| **审批 Gate** | 高代价扫描弹审批 dock、记忆作用域（仅本次/本会话/始终询问）、审计留痕 | DB-GPT Approval Center（内置） | 内置能力，无需 MCP |
| **文档知识库**（可选） | 引用溯源 chips 归档、Q→SQL 样例同步到团队知识库、纠错提案进待审队列 | 钉钉文档 / Notion / Confluence | 钉钉：`https://aihub.dingtalk.com/#/mcp`；Notion：Connector 设置页开启 |
| **沟通协作**（可选） | 大扫描审批请求推群、导出完成通知、纠错提案 @ owner | 钉钉 / 飞书 / Slack | 钉钉/飞书：Connector 设置页开启；Slack：待接入 |
| **工单事件**（可选） | 语义提案（✏️ 纠错）自动建工单跟踪审批发布、超阈值导出建审计工单 | 钉钉待办 / Jira / Linear | 钉钉待办：已通过 DingTalk 连接器接入；Jira/Linear：Connector 设置页开启 |
| **对象存储**（可选） | 导出文件（CSV/Excel）自动上传到 OSS / S3 并生成签名 URL 分享 | 阿里云 OSS / AWS S3 / MinIO | 待接入 |

## 必需 vs 可选

**必需**（无这些能力本套件无法运行）：
- 语义层（可以是"未激活"状态，套件会 fail-soft 降级为 `DBSummary` 表摘要，但会显式标注水位线）
- 数据源（至少一个只读从库或只读账号）
- 审批 Gate（核心 enforcement 点，不可绕过）

以上三项均为 DB-GPT **核心内置能力**，不需要额外配置 MCP。

**可选**（连上后体验升级）：
- 文档知识库：让引用溯源可归档、样例库可跨团队共享
- 沟通协作：让高代价审批、导出完成、语义纠错可推送到人
- 工单事件：让语义提案、超阈值导出有可跟踪的工单
- 对象存储：让导出文件可直接分享给外部

## 无连接器时的默认行为

所有技能在**没有任何外部连接器**的情况下均可完整运行，降级路径：

| 场景 | 默认行为 |
|:---|:---|
| 引用溯源归档 | 溯源 chips 在对话内展示，不写外部文档 |
| 大扫描审批 | 弹审批 dock 在会话内等确认，不推群 |
| 语义纠错提案 | 写入 `semantic.proposals` 队列，在语义中心页待人审，不建工单 |
| 导出文件交付 | 落盘到 `/outputs/`，以文件卡形式在对话内交付，不上传对象存储 |

## 与 `suite.yaml` 的关系

本套件同时携带 DB-GPT 项目自定义的 `suite.yaml`（loader 契约），声明：

- `execution: react` — 编排策略（P0 仅 react，flow 为 P1 预留）
- `tools.allow: [semantic_search, schema_link, nl2sql, sql_execute, export_csv]` — 会话内可调用工具集
- `tools.deny: [ddl, shell]` — 破坏性能力显式排除
- `context_defaults.semantic_model: required` — 语义模型为必需绑定
- `approval_overrides` — 4 条加严规则（仅可加严，enforcement 在核心 gate）
- `routing.keywords: [查, 统计, 导出, GMV, 客单价, top, 环比, 明细]` — 首页自动路由评分依据
- `recommended_questions` — 5 条首页推荐问题
- `semantic.layer: mysql_prod` — 绑定的语义层实例

`plugin.json`（本套件根目录 `.qoder-plugin/plugin.json`）是 AntWork 官方专家套件规范要求的元数据；`suite.yaml` 是 DB-GPT 项目内部 loader 的 manifest。二者共存，各服务其运行时。

## 后续扩展

以下能力计划在 P1/P2 接入：

- **Semantic-as-API / MCP**（P2）：把语义层抽为独立 MCP Server，跨套件复用
- **ChatBI 数据集分享**（P1）：与 `db-analysis` 套件联动，把取数结果一键转为分析数据集
- **审计导出到 SIEM**（P2）：把 approval 决议流水导出到企业 SIEM 系统
