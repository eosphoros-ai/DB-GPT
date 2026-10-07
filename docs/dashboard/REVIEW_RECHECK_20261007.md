# 2026-10-07 评审前补验

后续已完成实际 Docker 和历史 live 回放，并补充精确 mypy 基线，见 [剩余验收记录](REVIEW_REMAINING_20261007.md)。下文首次失败与当时跳过情况保留为历史过程。

受测代码从 `019c49ca` 接续，Python 修复提交为 `88cc13a0`，另含与本记录一起提交的前端修复和 grpcio 补丁。最终 SHA、对应 CI 和上游审批状态以 [PR #3278](https://github.com/eosphoros-ai/DB-GPT/pull/3278) 正文为准。旧日期的证据保留原有范围，不与本次数字累加。

## 修复范围

- 通用 Python 工作流改为安装锁定的 workspace 成员、执行实际的 `dbgpt` 包测试，并更新路径过滤、JUnit/覆盖率汇总和独立并发组。保留 `pip check`，不将安装失败算作测试通过。
- aiohttp 更新到满足现有 LiteLLM 的版本；排除生产工具函数的意外 pytest 收集，修正异步测试的 fixture/参数化，并隔离数据库与全局变量。临时文件不再依赖 Windows 不允许的打开句柄或文件名；shell 测试使用 PATH 中实际选择的 Bash。
- 默认 uv 配置不再引用不存在的依赖组。`uv.lock` 由 uv 0.12.22 生成；aiohttp、aiosignal、yarl、aiohappyeyeballs 是第一次更新涉及的四个包。
- 第一轮 CI 的 macOS ARM64 / Python 3.10 被 grpcio 1.71.0 的错误 wheel 架构元数据阻塞：文件名是 universal2，内部 WHEEL 标签却是 x86_64。1.71.2 的两者一致，后续仅升级该补丁版本，未跳过平台检查。
- 保留上游 Wiki 工具和共享执行器，为未连接知识空间的 Agent 初始化 Wiki 可用性标记。
- 修复 AWEL 布尔参数绑定和图标比例、侧栏 logo 尺寸、背景资源路径，以及 dev 后生产类型检查重复加载 Next 生成的 validator。新增回归同时证明错误的应用类型仍会导致检查失败。
- Python 直接托管静态导出时，详情页和分享页缺少动态路由回退，直接访问/刷新会 404。补齐固定 HTML 映射，保留独立的新建页面和既有会话分享；12 项回归覆盖有无尾斜杠、缺失产物返回 404 和 API 不被遮挡。
- 实际启动日志暴露临时 SQLite 连接先删除文件、后关闭句柄，在 Windows 会留下锁定文件。调整关闭顺序，并修正 SQLite 测试的资源回收。单行查询的旧断言与上游既有“行列表”返回值不一致，现覆盖单列、多列和空结果；未改查询返回语义。

发布权限、批注保留旧基线的冲突策略、固定分享令牌与 public_slug 最新别名均保持不变。

## 本机结果

Windows x64，Node 20.20.2 / npm 10.8.2，Next.js 16.3.8，隔离 Python 3.11.9 环境。

| 检查 | 本次结果 |
| --- | --- |
| 核心 Python | 740 通过，0 失败、0 跳过；从最终选择的锁定环境运行。 |
| Dashboard 后端 | 静态路由补丁后 650 通过，4 个本机未配置的 MySQL/Redis 用例跳过；先前 638 项及新增 12 项不重复相加。 |
| 执行器、子代理、沙箱与相关 API | 223 通过，8 个 Docker 用例跳过；此前三个 Windows 失败已修正。 |
| SQLite 连接器 | 22 通过；包括真实临时数据库使用后删除及重复关闭。通用 Python CI 单独运行此套件并保存 JUnit。 |
| Python 格式与 lint | 按 Makefile 分组执行 Ruff 0.16.10，全部通过。 |
| 工作流 / 锁文件 | actionlint 1.7.12、uv lock --check、冻结安装与 pip check 通过。 |
| 前端类型 / lint | 独立 TypeScript 通过；ESLint 0 错误、88 警告。 |
| 构建契约 / 既有前端 / Dashboard 组件 | 分别为 38 通过、2 个 POSIX 跳过；20 通过；304 通过。 |
| dev Chromium | 首轮 125 通过、3 项超时、7 跳过；三项定向重跑全部通过。不是首轮全绿。 |
| Fast Refresh | 可见文本更新与恢复均不重载文档，输入保留，源码哈希恢复；该专项无页面错误、控制台诊断或 HTTP 失败。 |
| 生产构建 / 静态导出 | 均通过，每次核验 64 个 HTML 页面、2,022 个本地资源引用，构建内类型检查通过。 |

dev 全套运行期间 Next 因接近内存阈值重启，三项超时位于该运行过程；重跑通过不构成冷启动性能保证。完整开发日志仍出现组件库 findDOMNode 弃用提示及部分图片尺寸/加载建议，不声称全站开发控制台零警告。

grpcio 补丁后的首次本机 pytest 命令未指定独立临时目录，公共 `pytest-of-ROG` 目录的
Windows 权限使 105 个 fixture 初始化失败（635 项通过）。改用任务内全新 `--basetemp`
后完整重跑为 740 项通过；未修改系统目录权限，也未跳过相关测试。

## 真实后端场景

在独立 SQLite 元数据库先初始化上游元数据，再执行 Alembic 到 `20260929_dashboard_share_secrets`。使用仓库脚本重建合成 Walmart 和 Apple 历史公开财务示例，以真实 API 与 SQLite 查询验证，未模拟 API/SSE。

- 两个示例均完成编辑标题、保存、重新打开、修订号增长、查询刷新、发布固定快照，以及匿名桌面和 390px 手机访问。
- 每个看板包含五个组件；KPI 与独立 SQLite 计算比较：Walmart 为 746,113,337.36，Apple FY2024 营收为 391,035 百万美元。
- 验证发布页没有编辑入口、手机无横向溢出；图表连续三次截图稳定，页面错误为空。
- 开发模式、Next 生产服务模式、Python 直接托管最终静态导出的模式均通过。

这验证了数据查询和编辑发布链路，不包含本轮新的 AI 生成评测。七个既有 live 用例依赖指定的历史模型资产、ID 和环境，仍显式跳过；新建的两个示例不替代它们。#3277 的真实模型、知识库、AWEL、定时任务和分享回放验收另记在其 PR 中。

静态托管补验使用实际导出的 `web/out`，挂载到隔离测试包目录后调用正式的
`mount_static_files`，通过同一 Python 服务的真实 API 完成上述两例。修复前列表/新建页
为 200，而 `/dashboards/example-id/` 与 `/dashboard-share/example-token/` 为 404；
修复后实际详情和匿名分享均可直接加载与重新打开。HTML 路由不改变 API 的鉴权或分享策略。

## CI 与剩余范围

`88cc13a0` 的 [Dashboard CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/37515113558) 为 **642 通过、0 失败、0 跳过**，包含临时 MySQL 8.0 / Redis 7.2。已下载 JUnit 核对。

同提交的 [首轮通用 Python 矩阵](https://github.com/jcsdxhe/DB-GPT/actions/runs/37515113453) 中，Ubuntu 3.10/3.11 与 macOS 3.11 各 **740 通过、0 失败、0 跳过**；macOS 3.10 在上述 grpcio 平台检查处失败，未开始测试。补丁后最终提交的四环境结果单独链接在 PR 正文。

grpcio 补丁提交 `cafa890804c63097de60a3b59d3828106aa7ba39` 的
[四环境重跑](https://github.com/jcsdxhe/DB-GPT/actions/runs/37517824816) 已全部成功，
每个环境均 **740 通过、0 失败、0 跳过**，已分别下载 JUnit 核对。
后续包含前端与文档的最终提交，仍单独记录其 CI，不以此中间提交替代。

- 全核心 mypy 仍失败：1085 项诊断、191 个文件；未改动的另一分支核心代码同样有大量诊断，但不是精确上游基线，不能据此把每条错误都归为已有问题。没有关闭类型检查；全仓类型债未在本轮清理。
- Docker Desktop 已尝试启动，但本机引擎未就绪，8 项实际容器验收未执行。全仓 `make test`/doctest、生产身份/多租户、原生 SQL Server/Oracle、长时间负载与真实部署不在通过范围。
- 两个 PR 各自对新抓取的 main 无冲突，不能推断它们彼此无冲突。合入次序和共享修改归属仍需维护者决定。

## 复现入口

前端按 [开发指南](DEVELOPER_GUIDE.md) 执行类型、lint、组件、构建和导出命令。
开发模式用 `npm run dev -- -p 5792` 启动，再设置
`DASHBOARD_E2E_BASE_URL=http://127.0.0.1:5792`，运行
`npm run test:e2e:dashboard -- --workers=1 --retries=0`。不要把不具备资产的 live 套件隐藏掉。

通用 Python 工作流的核心命令：

```sh
uv sync --frozen --package dbgpt-app --package dbgpt --package dbgpt-mono --extra base --extra collaboration --extra proxy_litellm
uv run --no-sync python -m pip check
uv run --no-sync python -m pytest --pyargs dbgpt
uv run --no-sync python -m pytest packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/tests/test_conn_sqlite.py
```

Windows 可为 pytest 指定新的任务专用 `--basetemp`；该目录由 pytest 管理，勿指向已有用户文件。
真实数据案例用 `examples/dashboard/build_demo_databases.py` 重建数据库，再导入
`examples/dashboard/schemas/` 中的 schema；在独立元数据环境中完成编辑、刷新和固定快照发布。
