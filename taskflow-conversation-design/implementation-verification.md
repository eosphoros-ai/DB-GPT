# 多轮对话工作流：实现与验证记录

日期：2026-11-01。入口：<http://localhost:3000/taskflow/editor>。

## 实际实现

生成助手使用有状态的结构化生成。每轮结合最新画布、用户消息、澄清回答与可用能力目录，返回澄清、完整候选或失败。服务端校验完整 JSON、节点字段、串行图、局部修改范围、资源与编译结果；格式或结构错误最多修正两次，总生成预算为 180 秒。生成阶段不执行业务工具。当前输出函数已确定 `generation_result/1` 协议，模型省略该常量时由服务端补齐；显式返回其他协议仍拒绝。

空白流程的首次合法候选自动应用；第一次需求提交若返回带假设的候选，或初次描述不超过 20 个字符，服务端先澄清具体目标，保持空白画布，避免将模型扩展的业务范围直接应用。用户补充需求后继续生成，避免反复确认已给出的信息。已有流程先预览差异，再应用或放弃。支持选中节点修改、撤销最近一次应用、取消生成，以及手动修改使旧候选过期。未选择的数据源和知识库不会作为默认绑定提供给生成模型；已有引用可以保留，新增引用需要用户明确指定。生成模型目录限制为用户选中的模型、明确提及的模型及已有节点模型，避免默认切换。

会话、需求记录、请求结果、候选与运行证据持久化在元数据库的 `taskflow_generation_session` 表中，采用存储版本 CAS 校验。浏览器通过 localStorage 保存会话 ID，刷新后恢复该浏览器的编辑检查点。生成任务使用异步提交与轮询；短暂断线继续查询原任务，不自动重新生成。

资源缺口以节点实际绑定的查询或检索能力为准；模型把“不连接数据库”描述成缺口时不会将纯文本 Agent 判为缺少数据源。

试运行继续使用现有 TaskFlow → AWEL 执行链，新增会话专用 SSE 接口。成功要求真实业务节点全部返回成功标记且调用没有报错。发布需匹配当前草稿版本、快照和资源目录的成功运行证据。修改会清除验证，单次成功只证明该版本在该次输入下运行成功。

新入口保存正在运行流程的草稿时只更新编辑检查点，保留原正式实体和已注册 DAG。未发布正式草稿写入 DAO，不注册执行 DAG。发布才调用正式流程更新，并在会话中保存发布快照及验证记录。

正式草稿写入后按 UID 回读，兼容现有 DAO 创建后的完整请求查询可能返回空值的行为。前端同时识别项目统一错误正文的 `err_msg` 与 FastAPI 的 `detail`，保存和试运行失败会展示具体原因。

## 实际接口

统一前缀：`/api/v2/serve/awel/taskflow/generation-sessions`。沿用现有 flow API 的认证依赖。

| 方法 | 相对路径 | 行为 |
| --- | --- | --- |
| POST | 空路径 | 建立编辑会话 |
| GET | `/{sid}` | 恢复检查点、查询请求结果 |
| PUT | `/{sid}/draft` | 同步手动编辑与版本 |
| POST | `/{sid}/messages` | 幂等提交生成请求 |
| POST | `/{sid}/requests/{rid}/cancel` | 取消指定请求 |
| POST | `/{sid}/candidates/{cid}/apply` 或 `discard` | 应用或放弃 |
| POST | `/{sid}/undo` | 撤销最近一次应用 |
| POST | `/{sid}/debug` | 对当前版本真实试运行，返回 SSE |
| POST | `/{sid}/save` | 保存检查点或经验证发布 |

## 代码位置

- 后端：`packages/dbgpt-serve/src/dbgpt_serve/flow/service/generation_service.py`、`flow/api/generation.py`、`flow/serve.py`。
- 前端：`web/hooks/use-taskflow-conversation.ts`、`web/components/taskflow/editor/ConversationPanel.tsx`、`DebugDrawer.tsx`、`web/pages/taskflow/editor.tsx`。
- API 与类型：`web/client/api/taskflow-generation.ts`、`web/types/taskflow-generation.ts`。
- 专项回归：`packages/dbgpt-serve/src/dbgpt_serve/flow/tests/test_generation.py`。
- 真实浏览器脚本：[browser-verification.cjs](browser-verification.cjs)；逐项结果：[browser-verification.json](browser-verification.json)。

## 验证

环境：本地生产模式 Next.js（3000）、实际 DB-GPT 后端（5670）、Google Chrome 与 Playwright。生成测试选择已启用的 `glm-5.3-flash`；浏览器脚本不 mock API 或 DSL。试运行使用当前抽屉选择的真实模型，运行 ID 与模型记录在逐项结果中。

- 最新后端专项测试：36 项通过（含真实 SQLite DAO 保存）；Ruff 格式与检查通过。
- 修改涉及的前端文件：ESLint 通过。
- 最新前端生产构建：通过。构建配置跳过完整类型检查；此前单独执行全仓 TypeScript 检查有既存错误，不能视为全仓类型检查通过。
- 原有 TaskFlow 测试：21 项通过、20 项因工作区已有模板文件缺失而失败；未恢复与本次无关的删除文件。
- 真实浏览器完整生命周期：通过。首次澄清和生成完成后，测试脚本在节点点击的导航等待中超时；截图确认节点已经选中。修正脚本的非导航点击等待后，重新打开浏览器恢复同一会话，完成后续全部步骤。此次为同一会话分段验证，不是一次不中断的脚本运行；恢复后脚本退出码为 0，页面异常为 0。

| 浏览器验证场景 | 实际结果 |
| --- | --- |
| 模糊需求澄清、补充需求后首次生成 | 使用真实 `glm-5.3-flash`，生成两个串行 Agent |
| 局部修改预览 | 仅改变选中 Agent 的目标，其他节点与画布保持不变 |
| 应用、撤销、放弃 | 应用后撤销恢复原 DSL；放弃保留原画布 |
| 手动修改与取消 | 修改标题使候选过期；取消请求后服务端状态为 cancelled |
| 未验证直接发布 | 服务端拒绝，页面显示“请先对当前版本成功试运行，再发布” |
| 真实业务试运行 | 抽屉选择 `deepseek-v4-pro`；两个 Agent 返回成功标记，页面显示同比增长 20% |
| 保存与刷新恢复 | 正式草稿保存成功；刷新恢复同一会话与原 DSL |
| 发布及后续草稿保存 | 当前验证版本发布成功；新草稿保存后，正式流程标题、DSL 和 running 状态保持不变 |
| 测试清理 | 删除本次新建的正式测试流程 |

真实运行 ID：`a686818fb9eb4611b430a5f6baff6162`。浏览器证据：[澄清](editor-clarification.png)、[生成画布](editor-generated.png)、[真实试运行](editor-debug-success.png)、[新草稿刷新恢复](editor-final.png)。逐项断言与时间见 [browser-verification.json](browser-verification.json)。

复现命令：在仓库根目录执行 `node taskflow-conversation-design/browser-verification.cjs`。需要以上前后端与模型已可用；脚本仅新建纯文本分析测试流程，成功完成后删除本次测试的正式流程。

## 工具运行展示更新（2026-11-01）

工作流节点卡片和编辑器试运行复用首页 `AgentTimeline`，由 `TaskflowAgentTrace` 将节点事件映射为同一工具时间线。支持工具图标、按调用拆分混合批次、同工具折叠、输入/结果展开、SQL 结果卡片，以及逐工具失败状态。节点结论与调用过程分开展示。调用数量按实际工具计算，不再把一组多工具调用算成一次，也不在调用刚出现时直接显示成功勾。

后端补充结构化 `action_input`、完整 `output` 和 `success`，保留所有本次执行事件；最终节点 marker 保留这些字段，后续历史回看可以展开。旧记录缺失或截断的工具输入/结果无法补回，不猜测结果归属。模型订阅/余额错误作为最终返回文本时也会使节点失败，避免错误结论被标为成功。

验证：31 项工具时间线测试、7 项 marker/错误判定测试、36 项生成会话回归通过；修改文件 ESLint、Ruff 和生产构建通过。Chrome 中使用明确的响应回放样例验证了首页工作流和编辑器的混合工具拆分、图标、SQL 表格及失败展示，无页面异常。此次真实模型调用分别遇到 GLM `403 SUBSCRIPTION_NOT_FOUND` 和 DeepSeek `402 Insufficient Balance`，未获得真实工具执行结果；回放 UI 验证不能等同于本次真实模型运行成功。

修正错误判定后，真实浏览器再次调用 DeepSeek：服务端运行状态为 `failed`，页面显示模型服务错误，不再显示“流程执行完成”。这项真实失败路径验证通过。

## 明确边界

- 新增业务节点只支持串行 Agent；并行、分支、循环、真实人工审批及断点续跑未实现。
- 新生成不能添加技能脚本、MCP 或 bash；已有且未改动的节点可保留原配置。该范围不是全平台工具执行策略的重构。
- 认证边界沿用现有实例/API key 模式，未新增逐用户 RBAC。资源目录仍遵循现有实例范围。
- 旧通用 flow API 保持原行为；保存隔离和发布验证只覆盖新增会话入口，不能据此宣称全平台发布门禁已统一。
- 会话 CAS 不等于跨数据库和运行 DAG 的分布式事务；发布快照是会话内归档，未实现完整独立版本服务或回滚系统。
- 跨浏览器会话发现、保留期限及会话删除管理尚未提供。
