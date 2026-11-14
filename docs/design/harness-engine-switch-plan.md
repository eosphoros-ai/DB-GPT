# DB-GPT Harness Engine 切换方案（pi / DSH / dbgpt）

> v2，2026-10-09（v1 误把 TaskFlow 节点级切换当重心，已按澄清重写：**首页 agent 本身的执行 harness 可切换**）
> 相关文档：`taskflow-redesign-plan.md`、`taskflow-agent-node-plan.md`、`agent_harness_design.md`、`harness-engineering-design.md`
> 目标：首页（DB-GPT AI Data Assistant）发起任务时，agent 可选 **pi**、**DSH（DeepSeek Harness）** 或 **dbgpt 自身**作为执行 harness；进展事件统一走现有 SSE 协议，前端运行态组件零改动。

---

## 1. 三个引擎的事实底座

| | dbgpt（现状） | pi | DSH（DeepSeek Harness） |
|---|---|---|---|
| 是什么 | 自研 ToolCallingReActAgent + ReAct 循环 | 极简可扩展 agent harness（repo `earendil-works/pi`，MIT，Node ≥ 22.19） | DeepSeek 开源 Agent Harness，"万物皆插件"，底层 Cordis 插件运行时 |
| 形态 | Python 进程内 | Node CLI / TS SDK | 开源框架；蚂蚁内部已有 **Piston 托管**版本 |
| 官方集成表面 | ——（进程内 API） | ① TS SDK `@earendil-works/pi-coding-agent`（进程内）；② CLI **print / JSON / RPC** 三种非交互模式 | **Piston DSH OpenAPI**：发布 Agent 模板 → Agent 实例 → OpenAPI 调用；首轮返回 `session_id`，后续带回即连续对话 |
| 适合 DB-GPT 的接入方式 | 进程内调用 | **RPC 子进程**（官方明确：跨语言/进程隔离 ≠ TS SDK，走 CLI Integration） | HTTP 客户端 + 事件映射 |
| 沙箱/审计 | dbgpt-sandbox（可选启用） | **工具以 pi 进程权限运行，无内置沙箱**（官方 Security 节） | Piston 托管自带沙箱、鉴权、Session 存储 |
| 模型接入 | SMMF / LLMClient（现有） | OpenAI 兼容 provider | 配在 Piston 模板里 |

三个引擎的**共同抽象形状**高度一致：给一个目标/提示 + 资源绑定 → 长程自主执行 → 期间吐结构化进展事件 → 结束后拿最终答案。这正是 "Harness" 的本义——模型之上的执行容器。

**pi 侧核心事实**（源：pi.dev/docs/latest）：
- TS SDK：`createAgentSession()` → `session.prompt()` → `session.subscribe(event)`；支持 `steer()/followUp()/abort()/waitForIdle()`；`SessionManager`（JSONL 持久化或内存）、`AgentSessionRuntime`（newSession/switchSession/fork）；模型、工具、扩展、系统提示全部边界可注入（`modelRuntime / settingsManager / resourceLoader / tools / customTools / excludeTools`）。
- CLI 集成：`pi --print`（一次性最终文本）、`pi --mode json`（JSONL 事件流，一次性）、`pi --mode rpc --no-session`（长驻 JSONL 双向通道：带 id 关联的命令/响应 + 事件流；可换模型、管理 session、应答扩展 UI 请求）。
- 完成信号语义：`agent_end` 后可能还有自动恢复/排队工作，**完成判定用 `agent_settled`**（官方推荐）。
- 正在流式执行时再发 prompt 必须显式选 steer/followUp 语义（与首页"连续追问再审"的会话语义对应）。
- 扩展生态：npm ~5500 扩展（MCP adapter、subagents、Langfuse/LangSmith observability、permission system、web-access 等）；支持 fork/rebrand（`package.json` 的 `piConfig.name/configDir`）。

**DSH 侧核心事实**：接入按 Piston 快速接入手册——① 创建并发布 DSH Agent 模板（模型/鉴权/沙箱/Runtime/Session 存储/调度/多版本实验全托管）；② skills 放 `.agents/skills/`、MCP 配 `.dsh/mcp.json`、更底层的能力走 Plugin；③ 拿 `template_id` + ak/sk 调 OpenAPI，首轮返回 `session_id` 续聊。选 Piston 而非自托管 DSH 的理由：DSH 自托管 = 承接 Cordis 插件治理负担（依赖管理、装载顺序、状态清理、配置治理、版本兼容），Piston 已处理完这套。

---

## 2. 语义边界：两个切换面

### 2.1 首页 agent（运行级整程切换）—— P0 核心

首页默认 agent 走专用端点 `POST /api/v1/chat/react-agent`（`chat_mode=chat_react_agent`）：

```
web/pages/index.tsx (~2180) 裸 fetch POST /api/v1/chat/react-agent
  → agentic_data_api.py:3915 chat_react_agent()
  → _react_agent_stream (1121) → _react_agent_stream_inner (1211)
  → _react_agent_stream_impl (1263)   ← 现在这页里直接驱动 ToolCallingReActAgent(max_retry_count=30)
```

关键现状（决定了方案形状）：
- 事件已是**结构化 JSON SSE**（不是 vis 内嵌文本）：`step.start / step.output / step.chunk / step.done / step.meta / plan.update / context.status / subagent.* / final / done`，经 asyncio `stream_queue`（:2135）中转，ManusLeftPanel 按 `type` 消费。
- 运行上下文 `ext_info` 已包含：skill_id/skill_name、database_name/db_type、knowledge_space_*、connector_ids、file_ids（会话文件作用域）。保存定时任务的 snapshot（`lastSentPayloadRef`）会 replay 原 payload → 引擎选择可自然随定时任务重放。

所以首页的切换语义就是**"一次对话任务整体交给哪个 harness 执行"**：

| 引擎 | 执行者 | 资源/事件来源 |
|---|---|---|
| dbgpt | 现有 `_react_agent_stream_impl` 内核（ToolCallingReActAgent） | 原样 |
| pi | conv 级 pi RPC 子进程（`pi --mode rpc`） | pi 事件翻译成 `step.*` |
| dsh | Piston DSH OpenAPI session | DSH 事件翻译成 `step.*` |

非 agent 产物（HTML 报告、文件、数据库写入等）仍经 DB-GPT 的产物通道落库——pi/dsh 引擎下通过 customTools/MCP 桥落回 DB-GPT（见 §4）。

### 2.2 TaskFlow agent 节点（节点级切换）—— P1

TaskFlow 混合流程里非 agent 节点（db_query/file_data/visualize/human_confirm…）操作 DB-GPT 资源体系，不应交给 pi/DSH；引擎只切换 **agent-kind 节点的子执行器**（插桩点：`taskflow_agent.py:_join_func` → HarnessRunner，事件仍走 `AgentStepEvent` → `vis-flow-step`）。这里复用与首页同一套 Runner，只是事件目标适配器不同。P1 再做，不影响 P0。

一句话：**DB-GPT 保留会话/资源/产物体系与 SSE 管道，把"模型之上的执行容器"换成可插拔的。**

---

## 3. 总体架构

### 3.1 分层

```
┌─────────────────── 前端（零协议改动）───────────────────┐
│ 首页：+ 菜单“Harness/执行引擎”选择器；ManusLeftPanel 按 │
│ type 消费 step.*（不感知引擎）                          │
└──────────────────────────┬───────────────────────────┘
                           │ POST /v1/chat/react-agent  (+ harness_engine 字段)
┌──────────────────────────▼───────────────────────────┐
│ agentic_data_api._react_agent_stream_impl            │
│   ├─ engine=dbgpt → 现有函数体（原样零改动）          │
│   ├─ engine=pi    → PiHarness.stream()               │
│   └─ engine=dsh   → DshHarness.stream()              │
│              统一事件契约: step.start/chunk/output/   │
│              done/meta/plan.update/final/done        │
├──────────────────────────────────────────────────────┤
│            HarnessEvent 中间事件层（引擎无关）        │
│   thinking_delta | tool_start | tool_output |        │
│   tool_end | turn_end | run_settled | final_text     │
├──────────────────────────────────────────────────────┤
│ HarnessRunner（共享）                                 │
│  ├─ PiRunner:   pi RPC JSONL 子进程（conv 级）        │
│  ├─ DshRunner:  Piston OpenAPI HTTP + session_id     │
│  ├─ DbgptRunner:（P1 给 TaskFlow 用，包装 run_react_agent）│
│  └─ McpBridge: DB-GPT tool-pack → stdio/HTTP MCP server│
└──────────────────────────────────────────────────────┘
```

设计要点：
- **HarnessEvent 是引擎无关的中间事件**；首页侧翻译成 `step.*` SSE，TaskFlow 侧（P1）翻译成 `AgentStepEvent`。两个消费端协议都不动。
- 首页两个分支（pi/dsh）不引入新端点、不改 SSE 帧 `_sse_event` 格式，只在现有事件词汇内映射。

### 3.2 请求协议

`POST /api/v1/chat/react-agent` 请求体增加字段（向后兼容，缺省 = 全局默认引擎）：

```json
{
  "chat_mode": "chat_react_agent",
  "user_input": "…",
  "model_name": "glm-5.3-flash",
  "harness_engine": "pi",
  "harness_options": {},
  "ext_info": { …
    "harness_engine": "pi"   // 落点：放进 ext_info，与 skill/db 等同等地位；定时任务 replay 自然带上
  }
}
```

读取位置：`chat_react_agent()` / `_react_agent_stream_impl` 解析 `ext_info.harness_engine`（空 = `[harness] default_engine`）。

### 3.3 引擎可用性探测（前端灰置）

新增轻量端点 `GET /api/v1/chat/harness/engines`（挂 agentic_data_api router）：

```json
[{"engine": "dbgpt", "available": true},
 {"engine": "pi", "available": false, "detail": "node not found"},
 {"engine": "dsh", "available": true}]
```

- pi 探测：`node_path` 存在 + `node --version` ≥ 22.19 + pi CLI 可执行。
- dsh 探测：Piston OpenAPI 健康检查（或配置存在即视为可用）。
- 首页选择器据返回灰置不可用项。

---

## 4. 各引擎详细设计

### 4.1 dbgpt（现状保持，零改动）

`_react_agent_stream_impl` 现有函数体原封不动，作为 `engine == dbgpt`（缺省）分支。这是本方案的零风险基线：**不选引擎时行为与今天完全一致**。

### 4.2 pi（PiHarness = PiRunner + 首页翻译层）

**进程生命周期**：**conv 级** RPC 子进程 —— 首次用 pi 引擎运行该会话时 spawn `pi --mode rpc --cwd <DBGPT_HOME/workspace/{conv_id}/pi_work>`，会话内复用（连答追问 = pi 连续 session 自然续聊），idle 超时（默认 30min）回收，崩溃自动重启一次（重启丢失 pi 侧记忆 → 下一轮 prompt 里自动补"此前进度摘要"）。LRU 上限防 proc 泛滥。

**pi session 持久化**：开启 `--session` 且 session 文件落 `workspace/{conv_id}/`（pi SessionManager 格式）→ 服务重启后仍可按 conv 续聊（P1 联动日志/审计再开）。

**一次 turn 的映射（pi → 首页 step.*）**：

| pi RPC 事件 | HarnessEvent → 首页 SSE |
|---|---|
| `message_update`(`text_delta`) | `thinking_delta` → 补进当前 step 的 `step.chunk`（前端已有消费）|
| tool 执行开始 | `tool_start` → `step.start{title:工具名}` |
| tool 产出 | `tool_output` → `step.output`/`step.chunk` |
| tool 执行结束 | `tool_end` → `step.done{status}` |
| `message_end`（权威完整消息） | `turn_end`，抽取最终 assistant 文本 |
| `agent_settled`（官方完成信号） | `final_text` → `final` + `done` |
| RPC 扩展 dialog 请求（扩展 UI 提问） | P0：自动应答默认选项 + 转成一条 `step.meta` 说明；P1：桥到首页 HITL |
| 每轮 assistant 文本 | 兼作 `plan.update`（若启用 todo 类扩展，P1） |

**资源投影（ext_info → pi）**：

| DB-GPT 资源 | pi 侧投影 |
|---|---|
| skill | skill 指令文本并入本轮 prompt 组装（P0）；P1 双向格式 |
| database / knowledge | 提示注入 + **MCP 桥工具**（SQL 查询/kb 检索等工具化，pi 经官方 MCP extension 连接） |
| connector_ids | 同上，对应 connector 的工具经 MCP 桥暴露 |
| file_ids（会话文件） | 系统链接/复制进 `workspace/{conv_id}/pi_work/`，pi 用自身读写工具操作 |
| model_name | 透传（见下） |
| 产物回转（报告/文件） | DB-GPT 产物类 tools（html 报告、写 workspace 文件）经 MCP 桥暴露给 pi 调用，产物仍走 DB-GPT 落库通道 |

**模型接入（推荐 1）**：pi 的 provider 指向 **DB-GPT 自身暴露的 OpenAI 兼容 API**（`/api/v2/chat/completions`，api_v2.py:71），`model=model_name` 透传首页模型选择器的值 → 模型注册/密钥/审计统一归 DB-GPT SMMF，pi 不感知任何密钥。备选：pi 自带 provider 配内部网关。

**安全基线（P0，pi 无内置沙箱）**：
- cwd 锁定 `DBGPT_HOME/workspace/{conv_id}/pi_work`（会话隔离）。
- 默认排除执行类内置工具（`excludeTools`: bash/edit 等），只留只读 + MCP 桥工具（**Option B：pi 只做决策，执行类操作全走 DB-GPT 工具产线/sandbox**）。
- P1 评估 **Option A：pi 整进程容器沙箱化**（网络/文件受限），放开更多原生工具。

**配置**（`configs/*.toml`）：

```toml
[harness]
default_engine = "dbgpt"            # dbgpt | pi | dsh
available_engines = ["dbgpt", "pi"] # 首页选择器白名单（dsh 待 Piston 资格）

[harness.pi]
node_path = "/usr/local/bin/node"   # Node ≥ 22.19（内部统一 runtime）
pi_cli = "/opt/pi/dist/cli.js"      # vendor 固定版本（版本锁定见 §7）
model_api_base = "http://127.0.0.1:5670/api/v2"  # 指 DB-GPT 自身 OpenAI 兼容 API
model_api_key = "..."               # 内部调用凭证（不出外部）
idle_timeout_s = 1800
max_children = 20
excluded_tools = ["bash", "edit"]
```

### 4.3 dsh（DshHarness：DshRunner + 首页翻译层）

**前提**：申请 Piston DSH 接入资格（内部注册，非阻塞 P0）。OpenAPI 具体形状**以 Piston 手册为准**（需登录态），以下是结构设计假设：

```
DshHarness.stream():
  1. conv → dsh session_id 映射查询（DB-GPT 存储层持久化，复用现有 meta 表思路）
  2. 无映射 → 首调 OpenAPI 建实例/会话（模板 = 预先发布好的 DSH Agent 模板）
  3. prompt 组装 = goal + 资源投影 markdown（skill 指令、db schema 摘要、kb 清单，与
     dbgpt 引擎侧的提示组装对齐，保证三个引擎收到等价任务信息）
  4. 调 OpenAPI（SSE）→ 事件映射：
       running/tool 类事件 → step.start / step.chunk / step.done（P0 粗粒度：running→
       step.start（工具摘要），完成→step.done）
       最终答复 → final + done
  5. 首轮拿 session_id，conv_id ↔ session_id 绑定持久化 → 后续续聊
```

- tool-pack → 复用 **MCP 桥**：`.dsh/mcp.json` 指向 DB-GPT 暴露的 MCP server（若 Piston 只支持远程 MCP，则桥用 HTTP/SSE MCP server——同一 DB-GPT 侧适配器两种暴露方式）。
- model：dsh 引擎下模型托管在 Piston 模板；首页模型选择器的值若 Piston 支持模型参数则透传，否则 UI 上灰置该选择器并提示"由模板决定"。

### 4.4 MCP 桥（三引擎共用组件）

DB-GPT tool-pack → 标准 MCP server 适配器：

```
                        ┌→ pi（官方 MCP extension，stdio 子进程）
DB-GPT tools ── MCP 桥 ┼→ dsh（Piston .dsh/mcp.json，stdio 或 HTTP/SSE）
                        └→（dbgpt 引擎不需要，直接函数调用）
```

- 暴露方式：stdio（pi 场景 P0）/ HTTP-SSE（dsh 场景 P1），同一份工具 schema 实现。
- 新组件，单测覆盖：工具描述 → MCP schema 映射、权限包名一致（联动 `ConfirmationRegistry`）。

---

## 5. 引擎能力矩阵与选型结论

| 维度 | dbgpt | pi | dsh |
|---|---|---|---|
| 部署形态 | 进程内（零依赖） | Node 22+，vendor 固定版本 | Piston 托管，无自建 |
| 沙箱/审计 | dbgpt-sandbox（可选） | 无内置（P0 工具收敛 / P1 容器化） | Piston 自带沙箱、鉴权、审计 |
| 事件粒度 | step.* 全事件（现网体验） | RPC JSONL delta 级，映射后体验对齐 | Piston SSE 形状待实测，P0 粗粒度 |
| 连续追问 | GptsMemory/StorageConversation（现有） | conv 级子进程 + pi session 文件 | Piston session_id 续聊 |
| HITL | 现有会话确认机制 | RPC dialog 子协议（P1 桥接） | 扩展 UI 协议（待手册验证） |
| 产物落库 | 原生（现有） | MCP 桥产物工具（原样走 DB-GPT） | MCP 桥（同上） |
| 扩展生态 | 自研 | npm ~5500 扩展（subagents/MCP/observability…） | DeepSeek 生态形成中 |
| 许可 | 自研 | MIT ✓ | 内部 Piston 托管 |
| 运维增量 | 无 | +Node 22 runtime、pi CLI vendor | +Piston 资格申请、OpenAPI 跟随 |

**选型结论**：默认 dbgpt；**pi 是 P0 唯一新增引擎**（RPC 子进程落地成本最低、事件粒度最好）；**dsh P1**（等 Piston 资格 + 手册）。三引擎并存非互斥，首页选择器白名单由配置控制。

---

## 6. 前端交互（首页）

- **入口**：`+` 菜单新增「执行引擎 / Harness Engine」项，带子菜单（复用 Task Flow 子菜单模式）：`dbgpt` / `pi` / `dsh`，当前项打 ✓，探测不可用的灰置并标注原因。备选：模型选择器（glm-5.3-flash）旁并列一个引擎胶囊控件。
- 状态持久化：localStorage（默认引擎切到 pi 时跨会话记住）。
- 步骤卡展示引擎徽标（ManusLeftPanel 传渲染标识即可，协议不动）。
- 引擎不可用时的运行报错：仍走现有 `step.done{status:failed}` + 失败文案（前端零新增组件）。
- i18n：zh/en 双写齐全（key 前缀 `harness.engine.*`）。

---

## 7. 分期落地

### P0（建议 1.5–2 周）
1. `harness/` 包骨架：HarnessEvent / PiRunner（RPC JSONL 客户端 + conv 级子进程生命周期）/ 首页 SSE 翻译层。
2. `agentic_data_api.py`：`ext_info.harness_engine` 解析 + `_react_agent_stream_impl` 顶部 dispatch（dbggt 分支 = 现有函数体原样）。
3. 资源投影：ext_info → prompt 组装 + file_ids → pi workspace；MCP 桥 v1（stdio，暴露 SQL/kb 等工具）。
4. pi 工具收敛（excludeTools 白名单）+ 会话隔离 workspace。
5. 探测端点 `/harness/engines` + 首页选择器（+ 菜单子菜单）+ 引擎徽标 + i18n 双写。
6. 配置 + 文档；单测（pi 事件映射用录制的 RPC JSONL fixtures 回放，不 spawn 真 pi）。
7. 真机冒烟：首页同一问题 × {dbgpt, pi}，步骤卡同构 + 连续追问（conv 复用子进程）+ 崩溃自愈。

### P1
1. DshRunner（Piston OpenAPI，等资格）+ session_id 绑定 + 事件细化。
2. HITL：pi RPC dialog → 首页确认 UI；`plan.update`/todo 扩展映射。
3. pi 沙箱强化（Option A 容器化评估）。
4. TaskFlow agent 节点级引擎切换（HarnessRunner 剪到 `_join_func`，event → AgentStepEvent）。
5. 观测：接 pi observability 扩展（`@langfuse/pi-observability-plugin` / LangSmith）。
6. benchmark：同一任务集 × 3 引擎质量/成本对比。

### 非目标（明确排除）
- 不自托管 DSH（Piston 托管即可）。
- 不改首页 `step.*` 事件词汇、不改 ManusLeftPanel 消费逻辑。
- 不把引擎选择编进 TaskFlow 编译期（P1 的节点级切换也是运行期参数）。
- P0 不做 subagent 编排（pi 的 subagents 扩展生态后续按需引）。

### 验收标准（P0）
- [ ] 首页同一问题 × {dbgpt, pi} 跑通，`step.*` 步骤序列同构，最终答案/产物落库一致。
- [ ] 选择器切换 → 立即生效（无需刷新/重建会话）；不可用引擎灰置 + 原因提示。
- [ ] pi 会话连续追问 ≥ 5 轮（conv 级子进程复用），上下文延续可感知。
- [ ] pi 子进程崩溃 → 自动重启一次并补进度摘要，再失败走 failed 事件。
- [ ] pi 工具收敛生效（无法直接执行 bash/edit；SQL/代码执行经 MCP 桥走 DB-GPT 产线）。
- [ ] i18n zh/en 双写齐全。

---

## 8. 风险表

| 风险 | 影响 | 缓解 |
|---|---|---|
| pi 无沙箱 + 工具全权限 | 执行类任务可任意读写文件/网络 | P0 excludeTools 收敛 + cwd 隔离 + MCP 桥执行；P1 容器化 |
| Node 22 runtime 引入 | 部署链路新增依赖 | vendor 固定版本 pi（install.sh pins 依赖），走内部制品源 |
| Piston OpenAPI 形状未知（手册需登录态） | DshRunner 设计有假设 | P1 开工前按手册修订；P0 不依赖 |
| 模型治理分裂（pi 直连外部模型） | 密钥/审计断链 | pi provider 强制指 DB-GPT 自身 OpenAI 兼容 API |
| 引擎间结果差异大 | 用户困惑 | P1 benchmark 对照；文案明确"引擎=执行容器，同模型下差异来自 harness 策略" |
| pi 版本演进快，事件/命令形状可能变 | RPC 集成脆弱 | vendor 固定版本 + record/replay fixtures 版本锁定 |
| pi/dsh 事件映射后 step.* 语义不齐（如 dsh P0 粗粒度） | 步骤卡体验降级 | 映射层单测；dsh 粗粒度标注在 UI（引擎徽标区分） |
| MCP 桥是新组件 | 新增故障面 | 先 pi only（stdio）；协议映射单测 |
| index.tsx 体量大（5300+ 行） | 回归风险 | 选择器独立小组件；请求注入集中在 react-agent fetch 一处 + snapshot 字段 |
| `_react_agent_stream_impl` 约 1800 行、状态多 | dispatch 改动容易误伤 | dbgpt 分支零改动原则；pi/dsh 分支独立生成器，不共享可变状态 |

---

## 9. 待评审问题

1. **DSH 资格**：Piston 接入是否已具备/可申请？决定 DshHarness 进 P0 还是 P1（当前方案：P1）。
2. **pi 版本策略**：vendor 固定版本（建议）vs 跟随 upstream。
3. **安全等级**：pi 工具收敛到只读白名单（当前方案）还是 Option A 容器化放开？需安全评审。
4. **引擎记忆边界**：pi 会话是"游离" harness（会话内自管上下文），与 dbgpt 引擎的 GptsMemory/知识注入不同——产品上是否要求三引擎的"记忆体验"对齐？
5. **`harness_engine` 落 `ext_info`**（当前方案）vs 请求体一级字段——考虑定时任务 replay 对齐，倾向 ext_info。

---

## 10. 参考资料

- pi 官方文档：https://pi.dev/docs/latest（SDK / CLI Integration / RPC Protocol / JSON Event Stream / Security）
- pi npm 包 `@earendil-works/pi-coding-agent`（MIT；Node ≥ 22.19；repo `earendil-works/pi`）
- pi 扩展市场：https://pi.dev/packages（MCP adapter、subagents、Langfuse/LangSmith observability、permission system、web-access 等）
- DSH：github.com/deepseek-ai/deepseek-harness；Cordis 论文 arXiv:2608.25512
- 蚂蚁内部：Piston DSH 快速接入手册（yuque piston/manual，需登录态）；ATA 文章《DeepSeek Harness（DSH）技术文档》11020762006、《Harness Engineering：当我们在聊 Harness 时》12020778013
- 本项目：`docs/design/taskflow-redesign-plan.md`、`docs/design/taskflow-agent-node-plan.md`
- 首页 agent 现状链路：`web/pages/index.tsx`（~2180 react-agent fetch）、`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`（3915 端点 / 1263 实现 / 2135 stream_queue）
