# PR #3278：2026-10-02 评审修复与验证

本轮从 `f1977798a96768f1fef54ee3f255c39283c1bf0d` 重做修复。此前另一环境报告的四个提交及 ZIP 未能取得，因此不引用其 SHA、测试数量或 SIGILL 结果作为本轮证据。#3277 和依赖版本保持不变。

本轮受测源码为 `ee3c9ed18309427ad0a3a83f8a70e0e52d2de2a3`：发布权限修复 `ede509c3`、Node 参数修复 `5feb80aa`、编辑保护及回归用例 `ee3c9ed1`。随后提交仅补充说明文档。

**最终 CI 已完成：** [Actions 36991047232](https://github.com/jcsdxhe/DB-GPT/actions/runs/36991047232) 在提交 `bc9b25e03df1f6a385f0b4b3cdd42a9009c12e29` 上的 Ubuntu、macOS 两个任务均成功。该提交相对受测源码 `ee3c9ed1` 只增加说明文档；本次补录结果也只修改文档，没有重跑回归。PR 仍待维护者评审，CI 成功不表示已批准或合并。

## 修复行为

| 问题 | 本轮处理 | 验证入口 |
|---|---|---|
| 保存请求尚未返回时继续编辑，迟到的响应覆盖新内容 | 保存回执更新服务端修订号；只有当前草稿仍等于送出版本时才替换编辑器内容。后续编辑及撤销历史保留，本地恢复草稿使用新修订号。 | `DashboardEditor.persistence.test.tsx`；浏览器 `dashboard-deterministic.spec.ts` |
| 单条批注可覆盖尚未保存的手工修改 | 与批量应用一致，未保存时阻止单条应用。单条或批量请求等待期间若继续编辑，则保留本地内容及旧修订号，显示远端版本提示，需明确选择后再加载。 | 同上；失败响应、干净草稿正常应用也有组件用例 |
| 发布查询的数据源检查遗漏发布绑定 | 原权限收集仅包含普通组件查询；现同时收集发布绑定及其联邦查询的数据源。在执行验证/查询前拒绝无权限数据源。匿名读取仍使用已冻结快照。 | `test_publish_authorization.py`，使用真实权限服务；正常发布用例使用 SQLite 元数据库与确定性查询连接器 |
| Dashboard 脚本覆盖用户自设 Node 堆参数 | 启动与构建脚本均先放默认 8192 MiB，再附用户 `NODE_OPTIONS`，交由 Node 解析；保留引号、多次设置和无关参数的原义。 | `toolchain-regressions.test.cjs`，两种脚本各 10 种参数组合，实测子进程 V8 堆限制 |

批注请求期间出现新编辑时，不会直接用新的服务端修订号保存旧草稿，从而避免把已应用的远端提案静默覆盖。用户仍需复制或协调本地改动后选择远端版本；没有实现自动合并。

## 本轮验证

环境：Windows，Node 20.20.2 / npm 10.8.2；在候选工作区运行 `npm ci`。后端使用已有 Python 3.11.9 / pytest 8.3.5 环境，`pytest.dashboard.ini` 指向本候选源码，未重新安装全套 Python 依赖。

| 检查 | 结果 | 范围与限制 |
|---|---|---|
| TypeScript | 通过 | `npm run typecheck` |
| ESLint | 0 错误、85 警告 | `npm run lint`；保留原有警告，不借本轮清理 |
| 构建契约与工具链 | 36 通过、2 跳过 | 共 38 项；Windows 不支持的两项 POSIX 信号测试显式跳过 |
| 既有前端逻辑 | 20 通过 | `npm test`：13 项 React 终态 + 7 项最终呈现 |
| Dashboard 组件 | 293 通过，54 个文件 | 含新增的 7 项真实编辑器组件测试；不是浏览器或真实后端测试 |
| Dashboard 后端 | 634 通过、4 跳过 | 638 项；新增 4 项发布权限测试。缺 MySQL 测试地址跳过 3 项，缺 Redis 地址跳过 1 项 |
| Python 静态检查 | 通过 | Ruff 检查本轮修改的服务与新增测试 |
| 生产构建 | 通过 | `npm run build`；64 个 HTML、1,992 处本地资源引用通过校验；本次未出现 SIGILL |
| 生产页面浏览器 | 两个套件、18 个不同用例通过 | Chromium，`npm start` 使用本次 build 产物；确定性生命周期 6 项、批注反馈 12 项。固定 API 输入，不代表真实模型/数据库联调 |

后端首次完整运行有 1 项新增正向测试失败：旧 `FakeDao` 的 owner 参数处理不支持真实权限模式。正向测试改用 SQLite 实际 DAO，并在建表前注册延迟加载的分享密文模型；没有修改业务代码来迁就测试。修正后 4 项专项及完整 638 项重新执行，结果如表。

新增发布权限负向用例在修复前确认：发布绑定及其联邦成员的无权限数据源未被提前拒绝，会进入验证路径；修复后均在验证/查询前拒绝。

浏览器首次两个套件运行 17 通过、1 失败：新增单条批注用例的测试接口拦截遗漏分页查询参数，未加载测试提案，等待按钮超时。按 URL pathname 匹配修正测试输入后，仅重跑受影响的确定性套件，6/6 通过；批注反馈套件原运行 12/12 通过。18 是不同用例数，不将重复运行相加，也不把首次失败抹去。配置中的 120 秒用例上限、15 秒断言等待及 30 秒操作等待均保持原样，自动重试为 0。

本机生产构建 ID 为 `mDyONfAcrbMEg3-zVJuQH`。本机只运行上述两个浏览器套件；推送后的完整前端矩阵由原有 CI 执行，结果如下。两平台实际使用 Node 20.19.6 / npm 10.8.2；各行分别计数，不把两个平台的重复用例相加。

| 平台与原始任务 | 构建契约 / 既有前端 | 组件 | 生产页面浏览器 | 构建与静态导出 |
|---|---|---|---|---|
| [Ubuntu](https://github.com/jcsdxhe/DB-GPT/actions/runs/36991047232/job/110787093659) | 38 / 20 通过 | 293 通过（54 文件） | 127 通过、7 跳过 | 通过；各校验 64 个 HTML、1,992 处本地资源引用 |
| [macOS](https://github.com/jcsdxhe/DB-GPT/actions/runs/36991047232/job/110787093873) | 38 / 20 通过 | 293 通过（54 文件） | 127 通过、7 跳过 | 通过；各校验 64 个 HTML、1,992 处本地资源引用 |

两平台的独立类型检查均通过，ESLint 均为 0 错误、85 条既有警告。浏览器使用 Chromium，运行 `npm run build` 产物及 `npm start`，不是 dev server；共发现 10 个套件、134 项，8 个套件实际执行，2 个 live 套件的 7 项因测试资源未配置而跳过。通过用例使用固定 API/SSE 输入，不代表真实后端、模型或外部数据库联调；CI 也未运行 Python 后端回归。

可从仓库根目录运行 `python -m pytest -c pytest.dashboard.ini -q` 验证 Dashboard 后端。在 `web/` 运行 `npm run test:dashboard`、`npm run test:build` 和 `npm run build`；浏览器设置 `DASHBOARD_E2E_START_SERVER=1`、`DASHBOARD_E2E_BASE_URL=http://127.0.0.1:5670`、`DASHBOARD_E2E_DISABLE_VIDEO=1`，执行 `npm run test:e2e:dashboard -- tests/dashboard-e2e/dashboard-deterministic.spec.ts tests/dashboard-e2e/home-annotation-feedback.spec.ts --workers=2 --retries=0`。生产服务由现有配置启动。

原始日志、JUnit 和组件 JSON 记录在本轮交付包中；通过数量仅来自本次执行，不与 [历史验证](VALIDATION.md) 相加。当前没有重跑真实模型、MySQL、Redis 或九项历史联调，也没有作生产部署验证。

## 合并关系

#3278 仍建立在 #3277 的早期快照上，不是与工具链完全独立的 PR。应先合入 #3277，再协调 Dashboard 对共享文件的后续改动；本轮仅同步 Node 参数语义，没有 rebase 或强推。完整关系、历史重叠路径计数及回滚边界见 [范围与依赖](PR_SCOPE.md)。
