# Dashboard 候选验证说明

## 2026-10-03 安全补丁与独立后端 CI

本轮将 Next.js / eslint-config-next 固定到 **16.3.8**，保留 React 18.3.1、
TypeScript 5.9.3 和构建内类型检查。更新限于 Next 配套包及其 SWC/Sharp 依赖；
锁文件的版本元数据、依赖范围、完整性哈希和官方下载地址已核对。

补丁包含 [Windows Next 服务漏洞修复](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36)
以及 [9 月安全版本](https://nextjs.org/blog/september-2026-security-release) 中适用于
自托管 Pages Router/SSG 和开发 MCP 的修复。Python 仅静态文件部署的暴露面不同；
官方同时披露了延期修复，因此不声称所有漏洞都已消除。本轮没有执行漏洞利用测试。

### 独立后端验证

新增 [Test Dashboard Backend](../../.github/workflows/test-dashboard-backend.yml)，
使用 Ubuntu、Python 3.11、固定 uv 0.12.22，从现有 `uv.lock` 建立新环境，执行
`pip check` 和完整 `pytest.dashboard.ini`。每次任务启动临时 MySQL 8.0、Redis 7.2，
具备独立并发组、只读仓库权限和 14 天 JUnit 留存；复现命令见 [开发指南](DEVELOPER_GUIDE.md#独立后端-ci)。

[首轮 CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/37130774532) 为 **641 通过、1 失败**：
MySQL 测试夹具缺少分享密文表。仅补齐夹具建表和清理后，提交
`dc61f34d466cf3e14f01d435079c658264bfd3e8` 的
[CI 重跑](https://github.com/jcsdxhe/DB-GPT/actions/runs/37131350823) 为
**642 通过、0 失败、0 跳过**，Python 3.11.17；已下载 JUnit 核对。
此前跳过的 3 个 MySQL 和 1 个 Redis 测试均实际执行。分享策略没有改变。
包含后续 Next 补丁的最终提交 CI 单独链接在 PR 正文，不用上述运行替代最终提交验收。

本轮还从锁文件建立了全新 Windows Python 3.11.9 环境，`pip check` 通过；
MySQL 夹具修复前的本机测试为 **638 通过、4 项外部服务跳过**。这与上述 CI
属于不同运行，数量不相加。新工作流不覆盖全仓 Python、运行时 Docker 或真实模型验收。

### Next.js 16.3.8 本机回归

受测工作树基于 `dc61f34d466cf3e14f01d435079c658264bfd3e8`，加上本次依赖补丁。
Windows x64，Node **20.20.2** / npm **10.8.2**，重新执行 `npm ci`。

| 检查 | 本轮结果 |
|---|---|
| 类型检查 | 独立 TypeScript 和生产构建内 TypeScript 均通过，未关闭错误检查。 |
| ESLint | **0 错误、88 警告**。 |
| 构建契约 | **37 通过、2 个 POSIX 信号用例跳过**。 |
| 既有前端测试 | **20 通过**；Wiki diff 断言也通过。 |
| Dashboard 组件 | **304 通过**，55 个文件。 |
| 生产构建 | 通过，核验 **64 HTML / 2,022 本地资源引用**。 |
| 默认静态导出 | `npm run compile` 通过，核验 **64 HTML / 2,022 本地资源引用**，构建内类型检查通过。 |
| 生产 Chromium | 发现 10 套件、135 项，**128 通过、7 跳过、0 失败、0 重试**。 |
| 材料检查 | 26 篇 Markdown、123 条本地链接、13 个浏览器夹具、4 个上传夹具和 4 个相对数据库路径检查通过。 |

浏览器使用真实生产前端与模拟 API/SSE，覆盖保存期间 Undo/Redo 等交互；7 个 live
用例因缺少既有模型资产和对应服务而跳过。本轮没有重跑较早记录中的全仓运行时套件，
也没有把其 **172 通过、3 失败、8 跳过**改写为通过。Firefox/WebKit、开发模式、
全仓 `make test` / `make mypy` 和真实模型验收不在本轮完成范围。旧云环境 SIGKILL
原因仍未知。后续最终提交的前端、后端 CI 结果分别链接在 PR 正文。

## 较早的 2026-10-03 本机接续核查（Next.js 16.3.0）

本轮应用源码为 `eceac9c7`，包含附件中的合并提交 `fdab9063`，并以重新获取的上游
`5905245a6750bafa636aa36a904b7fd4ead75334` 为基线。没有依次重放三个附件：
远端已有的数据源集合鉴权、Node 参数及部分编辑保护予以保留；仅补齐发布校验的 QUERY
权限条件、迟到回执的编辑/Redo/修订号保护，以及 Wiki 类型测试的 Windows 路径比较。
上游共享执行器和 Wiki 向导保留。批注继续采用保留旧基线并提示冲突的策略；
固定分享令牌与 `public_slug` 最新发布别名的策略均未改变。

Windows x64，Node **20.20.2** / npm **10.8.2**，前端重新执行 `npm ci`。
Python **3.11.9** 使用已有隔离依赖环境及当前工作树的源码路径，不等同于全新后端安装。

| 本轮检查 | 结果 |
|---|---|
| Dashboard 后端 | **638 通过、4 跳过**；跳过项需要 MySQL/Redis 外部服务。 |
| 执行器、子代理、沙箱及会话文件 | **172 通过、3 失败、8 跳过**；8 项需要 Docker，失败项见下文。 |
| 前端组件 | **304 通过**，55 个文件；新增回执竞争测试含同一 React 批次的响应次序。 |
| 构建契约 | **37 通过、2 跳过**；两个 POSIX 信号用例在 Windows 跳过。 |
| 既有前端测试 | **20 通过**；另行执行的 Wiki diff 断言通过。 |
| 类型与格式 | 独立 TypeScript、变更文件 Prettier 通过；生产构建内类型检查启用并通过。 |
| Lint | ESLint **0 错误、88 警告**。Ruff 0.11.5 的 Python 格式检查（1,621 文件）、导入与按 Makefile 范围分组的只读 lint 均通过。 |
| 生产构建 | `npm run build` 通过，核验 **64 HTML / 2,022 本地资源引用**。 |
| 静态导出 | 默认 `npm run compile` 通过，核验 **64 HTML / 2,022 本地资源引用**。 |
| 生产前端 Chromium | 完整发现 10 个套件、135 项：**128 通过、7 跳过、0 失败、0 重试**。包含保存期间 Undo 后保留 Redo 的新浏览器回归。 |

三个运行时失败已在未修改的上游运行时代码中同样复现：两个测试创建包含双引号的文件名，
不被 Windows 接受；一个 shell 管道测试选中了 Windows 的 WSL bash，无法消费测试的
Windows 路径。没有把这些失败改写为通过或新增跳过条件。历史云环境的 SIGKILL
原因仍未查明；本轮本机成功不代表已解释历史失败。

浏览器使用真实生产前端与模拟 API/SSE；7 个 live 用例仍缺少真实模型资产及后端。
本轮未执行全仓 `make test` / `make mypy`、真实模型或外部数据库验收。
本页的本机结果不能代替最终推送提交的 CI。两个 PR 分别与上述 main 无冲突，
但它们之间仍有 8 个共享路径冲突，合入顺序和后续协调需要维护者决定。

## 历史验证

**最新验证（2026-10-02）：** 未保存编辑保护、发布查询权限及 Node 参数修复已推送。[Actions 36991047232](https://github.com/jcsdxhe/DB-GPT/actions/runs/36991047232) 在 `bc9b25e0` 上的 Ubuntu/macOS 两个平台均成功；每个平台构建契约 38 项、既有前端 20 项、组件 293 项通过，生产模式 Chromium 127 项通过、7 项跳过，构建与静态导出通过。Windows 的本轮 Dashboard 后端为 634 通过、4 跳过。版本、原始任务链接、首次失败和未覆盖范围见 [2026-10-02 修复与验证](REVIEW_FIXES_20261002.md)。本页下文保留 2026-09-29 的历史验证，不将不同日期、平台或范围的用例相加。

验证日期：2026-09-29。候选依赖工具链提交 `ae095321f2f93d1536fdead00b1484d2637b96d9`，以保存的源码清单与补丁标识验证对象。完整集成版的历史记录与本候选分开，重叠用例不相加。

## 工具链依赖

工具链已提交 [官方 PR #3277](https://github.com/eosphoros-ai/DB-GPT/pull/3277)，当前开放评审，尚未合并。

[GitHub Actions 36565457316](https://github.com/jcsdxhe/DB-GPT/actions/runs/36565457316) 在 Ubuntu、macOS 全部成功。两者实际 Node 20.19.6 / npm 10.8.2，执行 npm ci、独立类型检查、lint、18 项构建契约及工具链回归、20 项既有前端测试、生产构建及静态导出。两种产物均核验 60 个 HTML 与 1,755 处本地资源引用。87 条警告的逐行基线归因不等于零警告。评审修复增加下载错误识别、事件退订与进程信号转发回归，其中两个 POSIX 信号测试在两个远端平台均实际执行。

## Dashboard 候选的 Windows 本机验证

| 范围 | 结果与边界 |
|---|---|
| 后端 | 1,036 通过、5 跳过。覆盖 Dashboard、任务、会话附件、上传数据集、连接器选择、规划编排、问答契约和 Agent 终态。 |
| SQL 与密钥专项 | 完整集成代码上的 104 项专项及 Dashboard 630 项检查通过；与上述检查重叠。未知方言、绑定、限制行数、硬链接错误及竞争不覆盖已有密钥均有用例。 |
| 前端组件 | 最终 53 文件、286 项通过，包含新建页数据源 v2 适配、规划确认、失败终态释放及迟到请求不会清除新操作状态。 |
| Python 锁文件 | `uv lock --check --offline` 通过。新增 redis 5.2.1，更新 dbgpt-app 的 SQLGlot/协作 extra 依赖；其余 563 个已有包条目保持原文不变。不是完整 Python 依赖安装测试。 |
| 类型 | 独立 TypeScript 通过；生产构建启用类型检查，未设置忽略错误。 |
| lint | 592 文件，0 错误、85 警告。按文件、规则、完整消息及去空白源码行对照工具链依赖，85 条重现、0 新增、2 消除。 |
| 生产构建 | 使用 `npm run build` 对应的项目脚本；64 个 HTML 与 1,992 处本地资源引用通过。Windows 原始 Next CLI 绕过项目文件句柄保护时曾失败，不作为通过证据。 |
| 浏览器 | 共 10 套件，8 套件实际执行、125 项通过；2 个 live 套件共 7 项跳过，0 失败、0 重试。逐套件范围与原因见下表。生产构建 ID 为 `QrGSuWiljHRRIVjtTJh6O`。 |

## Dashboard 跨平台 CI

[GitHub Actions 36565508485](https://github.com/jcsdxhe/DB-GPT/actions/runs/36565508485) 对提交 `cd95575f662be08d36a14586cf5689458f8eecff` 的 Ubuntu、macOS 前端矩阵全部通过。两套环境实际使用 Node 20.19.6 / npm 10.8.2，执行全新依赖安装、独立 TypeScript、lint、18 项构建契约及工具链回归、20 项既有前端测试、286 项 Dashboard 组件测试、生产构建、完整浏览器发现及静态导出。

| 平台 | 组件测试 | 浏览器测试 | 生产构建及静态导出 |
|---|---|---|---|
| ubuntu-latest | 286 通过 | 125 通过、7 跳过 | 通过 |
| macos-latest | 286 通过 | 125 通过、7 跳过 | 通过 |

每个平台发现 10 个浏览器套件：8 个实际执行、125 项通过；2 个 live 套件共 7 项显式跳过，0 失败、0 重试。通过数量按平台单独报告，不相加。浏览器使用生产前端及固定 API/SSE 输入，外部模型、真实后端和数据库连接不在该矩阵范围内。两套产物均核验 64 个 HTML 和 1,992 处本地资源引用；lint 为 0 错误、85 警告。

[首次运行](https://github.com/jcsdxhe/DB-GPT/actions/runs/36558272127) 的 macOS 构建在文件追踪收尾触发 EMFILE。提交 `19bd81d0` 将已有文件 I/O 并发保护同时用于 macOS，保留类型检查、输出追踪和资源一致性校验；上述完整矩阵验证了修复。GitHub 附件保留每个平台的 JUnit、Playwright JSON 和截图。

## 浏览器套件覆盖

仓库共 **10 个浏览器套件**。不指定文件过滤运行测试，发现 132 项：**8 个套件实际执行，125 项通过；另 2 个 live 套件的 7 项按环境门禁跳过**，0 失败、0 重试。原 44 项对应 4/10 套件；它们包含在 125 项中，不另行相加。

| 套件 | 通过 | 跳过 | 验证范围或跳过原因 |
|---|---:|---:|---|
| `agent-dashboard-live-evidence.spec.ts` | 0 | 6 | 跳过：需 Walmart/Apple/Northwind/Olist 既有模型生成资产、对应数据源与任务状态，以及 LIVE_AGENT 开关和资产 ID。 |
| `confirmation-continuity.spec.ts` | 2 | 0 | 新建页规划确认、会话与数据源连续性；模拟 SSE。 |
| `dashboard-deterministic.spec.ts` | 4 | 0 | 固定输入的列表、编辑、刷新、发布与匿名渲染。 |
| `editor-overflow.spec.ts` | 16 | 0 | 1440/1024 × 4 主题 × 明暗模式；核对 G2 轴标签实际位于视口内。 |
| `feedback-v93.spec.ts` | 26 | 0 | 组件库恢复、筛选保留未保存编辑、浮层可读性与控件布局。 |
| `fred-generalization-live.spec.ts` | 0 | 1 | 跳过：需指定 FRED 资产与 415 行时间序列数据、LIVE_AGENT 开关和资产 ID。 |
| `generation-timeout.spec.ts` | 2 | 0 | 生成超时、失败终态与旧事件隔离；模拟 SSE。 |
| `home-annotation-feedback.spec.ts` | 12 | 0 | 看板批注、澄清、重试、批量应用、编辑器与文件夹；不含已另存的首页场景。 |
| `rendering-fixes.spec.ts` | 36 | 0 | 图表坐标轴、系列、主题和长标签渲染。 |
| `template-workspace-v94.spec.ts` | 27 | 0 | 模板字段匹配、留存矩阵、文件夹生命周期、封面缓存与失败恢复。 |

两个 live 文件访问已有的真实模型成果及其数据源，并不在测试入口现场生成这些资产。隔离环境没有配置它们要求的资产 ID 和数据，因此 `DASHBOARD_E2E_LIVE_AGENT=0` 触发显式跳过；不能把随库确定性样例替代为这些历史模型成果。新增的防溢出、模板、批注三类套件使用固定输入或拦截 API，与首页改造无关，均已执行。

八个实际执行套件使用真实生产前端与模拟 API/SSE；下面两个案例才是单独的真实后端验收。完整结果按套件列示，并记录每个跳过原因。复现时启动同一生产构建，设置 `DASHBOARD_E2E_BASE_URL`、`DASHBOARD_E2E_DISABLE_VIDEO=1`、`DASHBOARD_E2E_LIVE_AGENT=0` 后，在 web 目录执行：

```sh
npx playwright test --config playwright.dashboard.config.ts --workers=2 --reporter=list,json
```

## 真实数据和模型边界

两个随库示例均使用候选后端、独立元数据库及重建的 SQLite 数据源，通过真实接口保存、重开、刷新、发布、匿名桌面与 390px 手机访问。每例五个组件，合成零售 KPI 为 746,113,337.36，Apple FY2024 收入为 391,035 百万美元；预期值从源数据库另行计算。该流程不调用外部模型，也不伪装成模型首次生成结果。

新建入口的确认/超时回归运行真实前端与 SSE 解析器，通过模拟模型传输验证对话和数据源绑定、明确确认、失败终态以及迟到事件不复活旧操作。原子命名参数与 T-SQL/Oracle 渲染用例不等于连接原生服务器。

生产截图等待图表动画结束，连续三张全页截图指纹一致后保存。页面运行错误、发布后的组件数和 KPI 文本另有断言。

## 环境和复现

后端使用 Python 3.11 的既有隔离依赖环境，通过显式源码路径及模块来源断言加载拆分候选；不是全新 Python 依赖安装测试。SQLite 上游元数据在启动前显式初始化，Dashboard 迁移运行到 `20260929_dashboard_share_secrets` 后关闭启动自动 DDL。凭据为空，模型地址限定本机不可用端口，确定性验收不调用付费模型。

前端依赖在候选目录执行 npm ci。Windows 本机验证使用 Node 22.23.2；Dashboard 独立的 Ubuntu/macOS 矩阵使用 Node 20.19.6 / npm 10.8.2，受测提交及完整结果见上文。工具链依赖的矩阵单独记录。常用命令：`npm run typecheck`、`npm run lint`、`npm run test:dashboard`、`npm run build`。浏览器使用 `playwright.dashboard.config.ts`，外部服务和真实模型用例需单独配置。

原始失败记录保留：Windows 路径映射、测试入口缺少 spawn 保护、旧分页预期、缺失翻译/问答依赖、浏览器旧断言与修复后的检查分开。仅列出的范围通过；没有把历史全仓基线失败写成全部通过。具体部署、模型语义及许可边界见 [已知限制](KNOWN_LIMITATIONS.md)。
