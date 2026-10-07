# Dashboard 开发指南

阅读 [设计说明](DESIGN.md) 后，按 [PR 范围](PR_SCOPE.md) 检查后端、共享服务、前端与工程配置。当前实现与共享会话、文件和定时任务集成，不能只复制看板目录完成安装。

## 环境与入口

前端按 `web/package.json` 使用 Node >=20.19.0、npm 10，锁文件为 package-lock.json。后端按仓库 [贡献指南](../../CONTRIBUTING.md) 建立环境，使用项目声明的 Python 依赖。Redis 协作依赖位于 `dbgpt-app[collaboration]` extra。

在仓库根目录执行材料检查及后端测试：

```sh
python scripts/dashboard/verify_pr_materials.py
python -m pytest -c pytest.dashboard.ini -q
```

在 web 目录执行前端检查：

```sh
npm ci
npm run verify:dashboard
```

`verify:dashboard` 包含 构建契约、TypeScript、全站 lint、Vitest 和 production build。lint 与类型检查覆盖全站，已归因的基线警告仍会输出；各项验证范围见 [验证说明](VALIDATION.md)。

## 全新环境安装与升级

### 独立后端 CI

[Test Dashboard Backend](../../.github/workflows/test-dashboard-backend.yml) 在 Ubuntu
和 Python 3.11 上独立运行完整 `pytest.dashboard.ini` 范围。工作流固定 uv 0.12.22，
为每个任务建立新虚拟环境，按现有 `uv.lock` 同时安装 `dbgpt-app` 的运行 extra 和
`dbgpt-mono` 的开发测试依赖；下载缓存不替代依赖安装。

本机复现同一依赖选择时，可把 `UV_PROJECT_ENVIRONMENT` 指向一个新目录，再执行：

```sh
uv sync --frozen --package dbgpt-app --package dbgpt-mono --extra base --extra collaboration
uv run --no-sync python -m pytest -c pytest.dashboard.ini -q -ra --junitxml=output/ci/dashboard-backend.xml
```

CI 为每个任务启动临时 MySQL 8.0 和 Redis 7.2 服务，并设置测试专用连接地址，
覆盖此前因外部服务缺失而跳过的 3 个 MySQL 用例和 1 个 Redis 用例。测试数据库随任务
销毁；不要把 `DASHBOARD_TEST_MYSQL_URL` 或 `DASHBOARD_TEST_REDIS_URL` 指向用户数据。
工作流使用只读仓库权限、独立并发组，并保留 JUnit 结果 14 天。它不运行模型推理、
运行时 Docker 套件或全仓 Python 测试。

### 运行环境

拆分候选的本机组合为 Python 3.11.9、Node 22.23.2、npm 10.9.8；工具链依赖另有 Node 20.19.6 / npm 10.8.2 的远端矩阵。后端在仓库根目录按锁文件安装需要的运行 extra；前端在 web 目录按 npm 锁文件安装：

```sh
uv sync --frozen --no-dev --package dbgpt-app --extra base --extra collaboration
cd web
npm ci --no-audit --no-fund
npm run build
```

模型提供方和数据库连接按项目配置单独设置。运行环境应指向新建的测试目录；迁移前备份已有元数据库。激活安装后的环境，在仓库根目录用目标 TOML 配置执行：

```sh
dbgpt db migration -c path/to/your-config.toml upgrade --alembic_ini_path pilot/meta_data/alembic.ini --script_location pilot/meta_data/alembic
```

配置中的元数据库与服务启动时使用的元数据库必须相同。Dashboard 迁移新库、从 v1 升级、已有资产/所有者保留及重复升级有专项测试。完整空库还需要上游元数据表：先按上游部署流程初始化基础元数据，再执行上述增量迁移；仅运行 Dashboard 的 18 个迁移不会生成所有上游表。服务端资源发现同时支持 wheel 与 editable 安装：优先使用包内模板，再查找安装分发目录；不会覆盖用户已有工作区文件。启动后继续执行示例导入、查询、保存、发布与匿名访问检查。

## 浏览器测试与固定输入

[fixtures/README.md](../../web/tests/dashboard-e2e/fixtures/README.md)解释固定输入、来源和更新方式。测试读取当前目录内的 JSON，不再依赖作者未入库的历史 evidence。先在 web 目录检查收集：

```sh
npm run test:e2e:dashboard -- --list
```

实际运行需可用的前端服务和 Playwright 浏览器；测试配置默认不自动启动服务。设置 `DASHBOARD_E2E_BASE_URL` 指向待验证的前端，再执行 `npm run test:e2e:dashboard`。可按配置使用 `DASHBOARD_E2E_BROWSER_CHANNEL=chrome`，或安装 Playwright Chromium。完整套件部分场景需要后端及已注册示例源；读取固定输入、拦截 API 的用例不构成真实模型验证。

共享接口已纳入后端及组件测试；排除的全站首页浏览器套件留在完整集成档案。真实模型、外部数据库、Redis、Docker 及写入资产的测试需各自准备隔离环境；不得因一个分组通过而标注另一分组已验收。

上传验收样例位于 [scripts/acceptance/fixtures/upload-samples](../../scripts/acceptance/fixtures/upload-samples/README.md)，由 optional_checks.cjs 读取。它们是运行输入；日志与截图是运行产物。部分既有浏览器脚本仍将新产物写入被 Git 忽略的 `docs/dashboard/evidence/`，这类写出路径不表示需要预先下载历史资料。

## 示例数据

```sh
python examples/dashboard/build_demo_databases.py --output output/dashboard-demo
```

命令会重建目标目录的同名数据库，只用于独立示例目录。该生成器包含合成零售与 Apple 财务摘录。[Walmart](demos/walmart.md)和 [Apple](demos/apple.md)分别说明来源、字段和核验步骤。

`data/dashboard_reference_sources/manifest.json` 的 database 字段以仓库根为基准使用相对路径。安装脚本注册数据源时仍向服务端传入本机解析后的绝对路径，不能把 manifest 的相对路径直接当作远端服务器路径。参考源安装脚本会下载及注册数据，静态材料检查不会执行下载和注册。

## 合同与迁移维护

修改组件或筛选能力时，同时检查 Pydantic、生成的 JSON Schema、TypeScript、Planner、编辑器、渲染、公开聚合和示例。Pydantic 合同测试会核对入库 JSON Schema；不要只添加一个前端标签。

新增查询方言须补充写操作、文件函数、参数和资源边界验证。标识符只能来自允许列表；查询取消的行为需要在对应驱动中验证。

当前增量包含 18 个迁移文件及迁移环境改动。迁移目录为 [dashboard migrations](../../pilot/meta_data/alembic/versions/)。实际依赖顺序以 revision/down_revision 为准；部署前按仓库迁移工具显式升级，并先备份。开发期 create_all 不替代正式迁移。

`20260929_dashboard_share_secrets` 将链接恢复密文表纳入迁移，兼容已由早期版本创建的同名表并保留密文；请求处理不再尝试建表。降级到该版本之前会删除恢复密文，独立授权表中的令牌哈希不变，因此已有链接的授权与链接恢复能力应分别检查。

三个旧兼容节点使用描述性文件名，但保留 `f8bd7ecc3d5f`、`cd2ea32f532b` 和 `2757edbd890f` 标识。这些标识已存在于本地数据库中，不能因为尚未合入官方而随意更换。三个旧节点到最新版本均需覆盖升级回归。

## Python 托管静态导出

`npm run compile` 生成 `web/out`。按上游打包流程将其内容放入
`dbgpt_app/static/web`，并启用 `service.web.new_web_ui` 后，Python 服务直接提供 HTML 与资源。
这条路径应独立于 `next start` 验证。

导出的动态页面目录仍叫 `dashboards/[id]` 和 `dashboard-share/[token]`；
`mount_static_files` 为实际 URL 提供固定 HTML 回退，并单独保留 `/dashboards/new`。
直接打开和刷新详情/分享链接应正常工作，有无尾斜杠均支持；缺少导出文件仍返回 404。
这些路由只提供页面，数据查询和分享权限继续由原有 API 校验。
相关回归包含在完整 Dashboard pytest 范围内。

## 记录结果

记录代码 SHA 或“基于某 SHA 的未提交工作区”、命令、环境、通过/失败/跳过数及日志位置。只有实际执行过的流程才记为通过。旧版验收、固定输入回放、模型生成和生产部署分别记录，见 [验证说明](VALIDATION.md)和 [历史资料说明](HISTORY.md)。
