# Dashboard 候选验证说明

验证日期：2026-09-29。候选依赖工具链提交 `b6f0c2ae6b4f9272f32292426317d6630767e84f`，以保存的源码清单与补丁标识验证对象。完整集成版的历史记录与本候选分开，重叠用例不相加。

## 工具链依赖

工具链已提交 [官方 PR #3277](https://github.com/eosphoros-ai/DB-GPT/pull/3277)，当前开放评审，尚未合并。

[GitHub Actions 36543862676](https://github.com/jcsdxhe/DB-GPT/actions/runs/36543862676) 在 Ubuntu、macOS 全部成功。两者实际 Node 20.19.6 / npm 10.8.2，执行 npm ci、独立类型检查、lint、10 项构建契约、20 项既有前端测试、生产构建及静态导出。两种产物均核验 60 个 HTML 与 1,755 处本地资源引用。87 条警告的逐行基线归因不等于零警告。

## Dashboard 候选

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

前端依赖在候选目录执行 npm ci。Windows 使用 Node 22.23.2；工具链 Node 20.19.6 的远端矩阵结论不替代 Dashboard 的矩阵测试。常用命令：`npm run typecheck`、`npm run lint`、`npm run test:dashboard`、`npm run build`。浏览器使用 `playwright.dashboard.config.ts`，外部服务和真实模型用例需单独配置。

原始失败记录保留：Windows 路径映射、测试入口缺少 spawn 保护、旧分页预期、缺失翻译/问答依赖、浏览器旧断言与修复后的检查分开。仅列出的范围通过；没有把历史全仓基线失败写成全部通过。具体部署、模型语义及许可边界见 [已知限制](KNOWN_LIMITATIONS.md)。
