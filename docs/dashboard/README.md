# Agent Dashboard

Dashboard 将自然语言分析变成可校验、可编辑、可保存和可发布的看板。Agent 先给出无 SQL 的业务规划；用户确认后生成受限查询；前后端围绕同一 Schema 完成编辑、筛选、修订和分享。

## 从这里开始

| 目的 | 文档 |
|---|---|
| 理解模块及生命周期 | [设计说明与两张架构图](DESIGN.md) |
| 创建、编辑、保存和发布 | [操作说明（PR 正文）](https://github.com/eosphoros-ai/DB-GPT/pull/3278) |
| 演示零售经营分析 | [Walmart：数据来源、制作与发布](demos/walmart.md) |
| 演示历史财务分析 | [Apple：数据准备、筛选与发布](demos/apple.md) |
| 安装依赖、运行检查、维护测试输入 | [开发说明（PR 正文）](https://github.com/eosphoros-ai/DB-GPT/pull/3278) |
| 理解部署身份、数据源授权与公开访问 | [安全与授权接入说明（PR 正文）](https://github.com/eosphoros-ai/DB-GPT/pull/3278) |
| 查字段及接口 | [Schema 与 API 说明（PR 正文）](https://github.com/eosphoros-ai/DB-GPT/pull/3278) |

## 代码入口

- [后端模块](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/)：Schema、SQL 校验、执行、权限、资产及发布。
- [Agent 工具](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/dashboard.py)：规划、确认与受控修改。
- [前端组件](../../web/new-components/dashboard/)：编辑器、渲染器、模板和发布窗口。
- [示例](../../examples/dashboard/)：Apple 财报摘录、合成零售数据库、固定 Schema 和快照。
- [浏览器固定输入](../../web/tests/dashboard-e2e/fixtures/README.md)：回归所需 JSON，随仓库维护。

固定历史发布使用冻结的数据；持续分享按已发布定义更新数据。可复现的合成零售数据与历史真实 Walmart 案例有不同来源和数值，详见案例页。

[已知限制](KNOWN_LIMITATIONS.md)记录产品边界。测试结果、提交版本和评审说明见 [PR #3278](https://github.com/eosphoros-ai/DB-GPT/pull/3278)。

## 数据库迁移与后端测试

`pilot/meta_data/alembic/versions/` 中的 Dashboard 迁移用于建立看板、修订、分享、
批注等表，并升级已有数据库。文件名中的版本号记录数据库结构的演进，
已有部署通过修订链升级，不能只保留最后一个文件。

同目录的 `env.py` 是 Alembic 的执行入口，与前端 `.env` 无关。
Dashboard 迁移使用当前连接；SQLite 使用批量改表模式，测试也可传入临时数据库连接。
`test_migrations.py` 覆盖空库初始化及旧修订升级。

仓库根目录的 `pytest.dashboard.ini` 配置 Dashboard 测试路径、包导入路径和外部服务标记，
供本地及 Dashboard 后端 CI 使用：

```sh
python -m pytest -c pytest.dashboard.ini
```
