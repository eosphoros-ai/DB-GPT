# Agent Dashboard

Dashboard 将自然语言分析变成可校验、可编辑、可保存和可发布的看板。Agent 先给出无 SQL 的业务规划；用户确认后生成受限查询；前后端围绕同一 Schema 完成编辑、筛选、修订和分享。

## 从这里开始

| 目的 | 文档 |
|---|---|
| 理解模块及生命周期 | [设计说明与两张架构图](DESIGN.md) |
| 创建、编辑、保存和发布 | [用户指南](USER_GUIDE.md) |
| 演示零售经营分析 | [Walmart：数据来源、制作与发布](demos/walmart.md) |
| 演示历史财务分析 | [Apple：数据准备、筛选与发布](demos/apple.md) |
| 安装依赖、运行检查、维护测试输入 | [开发指南](DEVELOPER_GUIDE.md) |
| 查看已执行检查及其边界 | [验证说明](VALIDATION.md) |
| 审查看板候选与工具链依赖 | [PR 范围与评阅顺序](PR_SCOPE.md) |
| 理解部署身份、数据源授权与公开访问 | [安全说明](SECURITY.md)、[授权接入](AUTHORIZATION_INTEGRATION.md) |
| 查字段及接口 | [基础 Schema](SCHEMA_V1.md)、[联邦扩展](SCHEMA_1_1_FEDERATION.md)、[API](API.md) |

## 代码入口

- [后端模块](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/)：Schema、SQL 校验、执行、权限、资产及发布。
- [Agent 工具](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/dashboard.py)：规划、确认与受控修改。
- [前端组件](../../web/new-components/dashboard/)：编辑器、渲染器、模板和发布窗口。
- [示例](../../examples/dashboard/)：Apple 财报摘录、合成零售数据库、固定 Schema 和快照。
- [浏览器固定输入](../../web/tests/dashboard-e2e/fixtures/README.md)：回归所需 JSON，随仓库维护。

固定历史发布使用冻结的数据；持续分享按已发布定义更新数据。可复现的合成零售数据与历史真实 Walmart 案例有不同来源和数值，详见案例页。

[已知限制](KNOWN_LIMITATIONS.md)记录当前边界。[历史资料说明](HISTORY.md)解释旧版本报告与个人结项材料的归档；这些材料不承担当前运行依赖。
