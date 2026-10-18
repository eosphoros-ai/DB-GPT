# Dashboard documentation / 数据看板文档

Dashboard is a saved, editable and publishable data-analysis workspace. This directory is the repository entry point for its documentation and business examples.

Dashboard 是可保存、编辑和发布的数据分析工作区。本目录提供文档导航与业务示例入口。

The design is maintained in the official documentation site, under **Development Guide → Dashboard Workspace**, with matching English and Chinese pages.

正式设计文档位于官方文档站的**开发指南 → 数据看板工作区**，中英文内容对应维护。

| Topic / 主题 | English | 简体中文 |
| --- | --- | --- |
| Architecture and data contract / 架构与数据合同 | [Design](../docs/design/dashboard.md) | [设计文档](../i18n/zh-CN/docusaurus-plugin-content-docs/current/design/dashboard.md) |
| Creation, AI changes and publication / 创建、AI 修改与发布 | [Workflow](../docs/design/dashboard.md#workflow) | [操作流程](../i18n/zh-CN/docusaurus-plugin-content-docs/current/design/dashboard.md#workflow) |
| Identity and source permissions / 身份与数据源权限 | [Authorization](../docs/design/dashboard.md#security) | [授权机制](../i18n/zh-CN/docusaurus-plugin-content-docs/current/design/dashboard.md#security) |
| Supported behavior and constraints / 能力与限制 | [Capability boundaries](../docs/design/dashboard.md#capability-boundaries) | [能力边界](../i18n/zh-CN/docusaurus-plugin-content-docs/current/design/dashboard.md#capability-boundaries) |
| Development checks / 开发验证 | [Validation](../docs/design/dashboard.md#validation) | [验证命令](../i18n/zh-CN/docusaurus-plugin-content-docs/current/design/dashboard.md#validation) |

<a id="数据库迁移与后端测试"></a>

## Deployment and upgrades / 部署与升级

For MySQL, initialize a **new database** with [v0.8.3.sql](../../assets/schema/upgrade/v0_8_3/v0.8.3.sql). For an **existing v0.8.2 database**, stop the service, back up and run [upgrade_to_v0.8.3.sql](../../assets/schema/upgrade/v0_8_3/upgrade_to_v0.8.3.sql) once before restarting. Skipping the upgrade can break existing scheduled tasks due to missing columns/indexes. SQLite follows the existing startup migration path. See [deployment requirements](../docs/design/dashboard.md#deployment) for older or partially upgraded databases and production dependencies.

MySQL **新装**执行全量 [v0.8.3.sql](../../assets/schema/upgrade/v0_8_3/v0.8.3.sql)；**已有 v0.8.2 部署**先停服、备份，执行一次增量 [upgrade_to_v0.8.3.sql](../../assets/schema/upgrade/v0_8_3/upgrade_to_v0.8.3.sql)，再启动新版。漏跑会因缺列或索引影响存量定时任务。SQLite 沿用原启动迁移入口。更早版本、部分升级的数据库及生产依赖见[部署要求](../i18n/zh-CN/docusaurus-plugin-content-docs/current/design/dashboard.md#deployment)。

## Examples / 示例

- [Walmart retail walkthrough / Walmart 零售操作案例](demos/walmart.md) — Chinese / 中文。
- [Apple financial walkthrough / Apple 财务操作案例](demos/apple.md) — Chinese / 中文。
- [Example data and Schemas / 示例数据与 Schema](../../examples/dashboard/)。
- [Browser fixtures / 浏览器固定输入](../../web/tests/dashboard-e2e/fixtures/README.md)。

Synthetic retail data and historical Walmart data have different sources and totals; the walkthrough explains which input to use.

合成零售数据与历史 Walmart 数据的来源、总额不同，使用前请按案例说明选择。
