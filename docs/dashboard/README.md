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

Dashboard 通过原有的 `db_model_initialization.py` 注册实体。SQLite 沿用项目原有的
建表和自动迁移入口，不分发另一套 Alembic 版本链，也不改共享 `env.py` 或本地修订号。
MySQL 沿用历史升级目录的全量、增量交付方式，入口集中在
[`assets/schema/upgrade/dashboard/`](../../assets/schema/upgrade/dashboard/)：

| 场景 | SQL | 执行方式 |
|---|---|---|
| 全新数据库 | [`dashboard.sql`](../../assets/schema/upgrade/dashboard/dashboard.sql) | 全量建库，与 `assets/schema/dbgpt.sql` 一致；不再执行增量脚本。 |
| 已有 v0.8.2 数据库 | [`upgrade_to_dashboard.sql`](../../assets/schema/upgrade/dashboard/upgrade_to_dashboard.sql) | 停止服务并备份后执行一次，再启动服务。更早版本先按历史目录升级到 v0.8.2。 |

增量脚本使用 `ALTER TABLE ... ADD COLUMN`、`ADD INDEX` / `ADD UNIQUE INDEX`
修改聊天记录及定时任务旧表，使用 `CREATE TABLE` 新建看板表；不删除业务数据，也不把任务显示名当作用户 ID 回填。
数据库名不是 `dbgpt` 时先调整脚本中的建库和 `USE` 语句。
增量脚本不是可重复执行的初始化器；已执行旧版 Dashboard 升级脚本或部分手工 DDL 的库，
应核对已有列和索引，仅执行缺失项，避免重复列或索引错误。

在仓库根目录安装项目后端测试依赖后执行以下完整命令（Bash）。测试路径、包导入路径和外部服务标记都在命令中显式给出，不需要额外 pytest 配置文件：

```sh
python -m pytest -c pyproject.toml --rootdir=. --import-mode=importlib -p no:cacheprovider \
  -o addopts= \
  -o "pythonpath=packages/dbgpt-app/src packages/dbgpt-client/src packages/dbgpt-core/src packages/dbgpt-ext/src packages/dbgpt-sandbox/src packages/dbgpt-serve/src" \
  -o "markers=mysql_integration: requires DASHBOARD_TEST_MYSQL_URL and a disposable MySQL database
redis_integration: requires DASHBOARD_TEST_REDIS_URL and a disposable Redis database" \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/tests \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_question_contract.py \
  packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tests/test_share_privacy.py \
  packages/dbgpt-serve/src/dbgpt_serve/scheduled_task/tests \
  packages/dbgpt-app/src/dbgpt_app/tests/test_multi_file_tools.py \
  packages/dbgpt-app/src/dbgpt_app/tests/test_olist_dashboard_case.py \
  packages/dbgpt-app/src/dbgpt_app/tests/test_uploaded_dataset.py \
  packages/dbgpt-app/src/dbgpt_app/tests/test_uploaded_dataset_registry.py \
  packages/dbgpt-app/src/dbgpt_app/tests/test_python_upload_api.py \
  packages/dbgpt-app/src/dbgpt_app/tests/test_workspace_provisioning.py \
  packages/dbgpt-app/src/dbgpt_app/tests/test_dashboard_skill_orchestration.py \
  examples/dashboard/tests
```

设置 `DASHBOARD_TEST_MYSQL_URL`（数据库名必须含 `test`）和
`DASHBOARD_TEST_REDIS_URL` 可运行真实服务集成测试；未设置时对应测试会明确跳过。
MySQL 测试会重建测试表，应只连接可丢弃的测试库。
