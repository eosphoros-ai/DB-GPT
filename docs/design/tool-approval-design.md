# 高危工具执行确认（Tool Approval）设计方案

> 状态：Draft v1 · 作者：chenketing.ckt · 关联：`docs/design/conversation-redesign-mockup.html`（前端时间线范式）
> 目标读者：agent 引擎 / 前端 / 安全
> 一句话：在工具真正执行前插入一道「风险分级 + 用户确认」的闸门，覆盖 dbgpt（react-agent）与 pi（harness）双引擎，前端以确认卡呈现，协议以 SSE 事件承载。

---

## 0. TL;DR

1. **现状**：DB-GPT 双引擎的工具执行链上**没有任何确认闸门**。connector 层有一套「step.confirm」休眠脚手架（`format_confirmation` 已实现但无调用方、前端无消费方），question 交互（gather 信息）是现有最接近的范式，但语义是「提问」不是「授权」。
2. **市面共识**（Claude Code / OpenAI Agents SDK / LangGraph / MCP / Microsoft Agent Framework）：确认 = **风险分级（auto / confirm / deny）→ 意图说明 → 用户决策（once / session / always 记忆）→ 拒绝作为 observation 回灌模型**。四阶段缺一不可。
3. **方案**：新增 `ToolRiskPolicy`（规则表 + toml 扩展）与 `ApprovalCenter`（注册 / 等待 / 决议 / 审计），在双引擎工具执行前统一 gate；前端确认卡走 SSE `approval.requested / approval.resolved` 事件；pi 引擎走 **HTTP 202 + 轮询 + token 兑换**（复用 question 的 202/轮询范式，规避 pi 侧超时不确定性）。
4. **分期**：P0 = 规则表 + dbgpt 引擎 gate + 确认卡 + 决议 API + session 记忆；P1 = pi 引擎 202 流程 + 意图分析 + always 记忆 + 审计表；P2 = shell/code 沙箱兜底 + SQL 写操作 confirm 档 + 多实例 redis 化。

---

## 1. 市面主流方案拆解（一手文档）

### 1.1 Claude Code（permission 体系，最完整的参照）

- **三档权限模式**：`default`（逐次询问）、`acceptEdits`（编辑类自动、其余询问）、`plan`（只读规划）、`bypassPermissions`（全跳过，需显式开启并二次确认）。
- **工具级规则**：`permissions.allow / ask / deny` 三张表，规则形如 `Bash(npm run *)`、`Read(//docs/**)`，支持通配符与参数模式匹配；命中 deny 直接拒绝并回灌 observation，命中 ask 弹确认卡。
- **确认卡四要素**：工具名 + 参数预览（命令以代码块呈现）、**意图说明行**（"Claude wants to run …" 一句话解释为什么要执行）、记忆下拉（once / this session / always）、拒绝按钮。拒绝后模型收到 rejection observation，不会重试同一操作。
- **高危拦截**：`rm -rf /`、`sudo`、`chmod 777`、`git push --force` 等模式默认落入 ask/deny 档；确认卡以**红色渐变头部**呈现高危标记。
- **并行 tool_calls**：多个待确认调用会**堆叠多张确认卡**，按发起顺序排列，用户可逐张或批量决议。

### 1.2 OpenAI Agents SDK（function tool 审批）

- `function_tool(needs_approval=...)`：可为单个工具或按参数模式（callable / 模板）开启审批；命中后 run loop 暂停，抛出 `ToolApprovalInterrupt`。
- **决议回灌**：`RunState.approve(approval_id)` / `reject(approval_id, reason)`；reject 的 reason 作为 tool result 回灌模型，模型据此改道。
- **审计**：`approval_id` 全链路可追踪，run state 持久化审批记录。

### 1.3 LangGraph（interrupt / Command 范式）

- `interrupt(payload)` + `Command(resume=decision)`：图执行在节点处暂停，payload 携带工具名 + 参数 + 风险级别；resume 携带 approve/reject + scope。
- **human-in-the-loop middleware**：官方提供 `interrupt_on` 配置，按工具名 / 风险级别路由到确认。
- **checkpoint 持久化**：确认状态随 checkpoint 落盘，刷新 / 重启后可恢复待确认卡。

### 1.4 MCP elicitation（协议层确认）

- `elicitation/create`：server 向 client 发起确认请求，schema 携带操作描述 + 参数 + 风险级别；client 回 accept / decline / cancel。
- **协议语义**：decline 必须作为 tool result 回灌模型；cancel 视为超时。协议层不规定 UI，但规定**决议必须回灌**。

### 1.5 Microsoft Agent Framework（approval 中间件）

- `@tool(approval_mode="always" | "never" | "conditional")`：工具级审批模式；conditional 按参数模式路由。
- **确认卡**：工具名 + 参数 + 意图说明 + 记忆下拉（once / session / always）。
- **审计表**：审批记录落表，可按 session / 用户查询。

### 1.6 共识提炼（四阶段范式）

| 阶段 | 内容 | 缺失后果 |
|---|---|---|
| ① 风险分级 | auto / confirm / deny 三档，规则表 + 参数模式匹配 | 高危操作静默执行 |
| ② 意图说明 | 一句话解释「为什么要执行这个操作」 | 用户盲目点同意（确认疲劳） |
| ③ 用户决策 | once / session / always 记忆 + 拒绝按钮 | 每次重复询问 / 无法授权 |
| ④ 决议回灌 | reject / timeout 作为 observation 回灌模型 | 模型重试同一高危操作 |

---

## 2. DB-GPT 现状勘察（代码事实）

### 2.1 dbgpt 引擎（react-agent）工具执行链

- **唯一漏斗**：native function calling（`NativeToolCallAction`，`tool_calling_agent.py:248` → `:302`）与文本 ReAct（`ParallelToolAction` `:130` → `:228`，单步回落 `ReActAction` `:466`）最终都汇聚到 `ToolAction.run_tool`（`packages/dbgpt-core/src/dbgpt/agent/expand/actions/tool_action.py:162`）→ `:226 tool_pack.async_execute`。**gate 应插在此处之前**。
- 并行 tool_calls：`run_tools_batch`（同文件 `:312`）在 `:377` 以 `asyncio.gather` 并发执行多个 tool spec；多张确认卡需在此处**先注册后并发等待**。
- 流式推送：`stream_callback` 定义于 `agentic_data_api.py:2478`，队列循环按事件白名单转发（`:3704` 转发 question.* 等），需新增 `approval.*`。

### 2.2 pi 引擎（harness）工具执行链

- **桥接工具**：`run_harness_tool`（`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/harness_pi_stream.py:318`）在 `:371` 直通 `tool_bridge.run_tool` 执行。**gate 应插在 :371 之前**。
- **原生工具**：bash / edit / write 等保留在 pi 侧（`_CORE_TOOLS`），shell 类需走桥接 `shell_interpreter` 才自然进入 gate；pi 升级 hook 策略见 §7。
- **事件注入**：`push_conv_event` 旁路已存在（`:1316-1321`），`approval.requested` 走同一通道。
- **question 范式可复用**：question 交互已实现 HTTP 202 + 轮询 + token 兑换（`dbgpt_tools.ts` 通用路径：202 → 轮询 `/question/status` 2s 间隔 / 320s deadline → 带 token 重发执行）；pi 引擎确认走同一范式。

### 2.3 connector 层休眠脚手架（step.confirm）

- `ConfirmationRegistry`（register `:27` / resolve `:35` / wait_for `:43`）与 `format_confirmation`（`:80`，产出 `step.confirm` 事件 `:87`）位于 `packages/dbgpt-core/src/dbgpt/agent/resource/connector/confirmation.py`，但 **should_confirm 全仓无调用方、step.confirm 无前端消费方**。
- serve 层 `packages/dbgpt-serve/src/dbgpt_serve/connector/api/endpoints.py:226-241` 有 `GET /pending-confirms` / `POST /confirm` 端点雏形；`dbgpt_ext/connector/catalog.json` 有 `confirm_actions` 字段。
- **结论**：这套脚手架语义是「connector 操作确认」，与工具执行确认同源但不同层；本方案将其**升级为 ApprovalCenter 的规则来源之一**（catalog confirm_actions → 规则表），不另起炉灶。

### 2.4 前端现状

- 时间线：`AgentTimeline.tsx`（block kind 联合需新增 `'approval'`）；QuestionDock 是现有最接近的交互范式（gather 信息），语义分离：question = 提问，approval = 授权。
- SSE 解析：`web/utils/react-sse-parser.ts:175` `processEvent` 白名单需新增 `approval.requested / approval.resolved / approval.intent`（未知类型当前被静默丢弃）。
- 历史回放：确认卡需随 step meta 持久化决议状态，回放时呈现最终态。

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│              前端（悬浮 dock + timeline 审计行）               │
│  composer 上方 dock：ApprovalCard / QuestionCard（叠放）      │
│  timeline：紧凑状态行 + observation 引用（审计，非交互）        │
│  SSE: approval.requested / approval.intent / approval.resolved│
│  REST: POST /api/v1/chat/approval/{id}/resolve                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     ApprovalCenter                           │
│  register(tool,args,ctx) → approval_id + asyncio.Event        │
│  wait(ttl=300) / resolve(decision,scope,reason) / audit       │
│  session 记忆（conv 级 pattern 白名单）/ always 记忆（toml）    │
└──────────────────────────┬──────────────────────────────────┘
                           │ classify(tool,args) → auto/confirm/deny
┌──────────────────────────▼──────────────────────────────────┐
│                      ToolRiskPolicy                          │
│  内置规则表（shell/sql/web/file/question）                     │
│  + toml [service.approval.rules] 扩展/覆盖                     │
│  + catalog confirm_actions（connector 层来源）                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ gate（执行前统一漏斗）
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  dbgpt 引擎          pi 引擎            未来引擎
  tool_action.py      harness_pi_stream   （同一 gate 接口）
  :162 之前           :371 之前
```

---

## 4. ToolRiskPolicy（风险分级）

### 4.1 三档语义

- **auto**：直接执行，不打断（只读 / 低风险操作）。
- **confirm**：注册确认卡，等待用户决议（ttl 默认 300s，可配）。
- **deny**：直接拒绝，回灌 policy observation（破坏性 / 越权操作）。

### 4.2 内置规则表（v1）

| 工具 | auto | confirm | deny |
|---|---|---|---|
| `shell_interpreter` / `code_interpreter` | 只读命令（ls/cat/grep/ps/df） | `kill/pkill/sudo/rm -rf/chmod 777/git push --force/curl 外网/nohup` | `rm -rf /`、`:(){:\|:&};:`、`mkfs`、`dd of=/dev/` |
| `sql_query` | SELECT/SHOW/DESC | INSERT/UPDATE/DELETE（带 WHERE） | 无 WHERE 的 UPDATE/DELETE、DROP/TRUNCATE（默认 deny，可配 confirm） |
| `web_fetch` | 公网 http(s) | 内网 IP / metadata 端点（默认 deny，可配 confirm） | — |
| 文件写（workspace 外） | — | workspace 内写 | workspace 外写 |
| `question` / `todowrite` / 只读 kb | 全部 | — | — |

### 4.3 toml 扩展/覆盖

```toml
[service.approval]
mode = "tiered"          # off | tiered | always（always = 全部 confirm，调试用）
ttl_seconds = 300
intent_analysis = true

[service.approval.rules]
"+confirm" = ["shell_interpreter:uv run pytest *"]   # 追加规则（工具:参数模式）
"-deny"    = ["sql_query:DROP *"]                     # 移除规则
"override" = { "sql_query:DELETE *" = "confirm" }     # 覆盖档位
```

参数模式匹配：支持 `*` 通配符与前缀匹配（v1），正则（v2）。

### 4.4 配置源与优先级（setting 可定义）

setting 界面是**策略的来源之一**，不是另一套机制：gate 永远只调一个 `policy.classify`，它看到的是多源合并后的规则集；UI 改规则不需要重启、不需要改代码，也不与 toml / 内置规则打架。

| 层 | 载体 | 谁改 | 权限 |
|---|---|---|---|
| L0 内置默认 | 代码内规则表（§4.2） | 研发 | 兜底，不可删 |
| L1 部署配置 | toml `[service.approval]`（§4.3） | 运维 / 部署 | 可覆盖 L0 |
| L2 产品 setting | DB 表 `approval_policy_rule` | 管理员 / 用户 | 可覆盖 L0/L1，受锁定约束 |
| L3 会话决议 | 内存 / conv meta（once/session/always） | 终端用户 | 只降档白名单签名，不改规则 |

合并优先级 **L2 > L1 > L0**，带方向约束：

- UI 只能**加严**（auto→confirm→deny 任意走）；放松受两条锁——组织托管的 deny 规则在 UI 显示锁图标不可降；内置 deny 降级需二次确认并留审计；
- fail-safe 方向（加严）永远开放；未知工具默认 confirm。

### 4.5 setting 界面定义面

- **全局模式**：off / tiered / always 三档开关；off 与 always 保存前弹影响说明确认；
- **工具级档位表**：每行一个工具（shell_interpreter / sql_query / code_interpreter / web_fetch / connector 写操作…）× 三档下拉，直接覆盖 L0 声明档；
- **规则编辑器**：tool + 参数模式（glob v1 / 正则 v2）+ 档位 + 优先级的增删改；带**试运行输入框**（policy playground）——粘一条命令 / SQL 实时显示命中哪条规则、落在哪档，规则写错当场发现；
- **白名单管理**：session / always 记忆条目列表，可撤销单条；
- **参数**：ttl、意图分析开关、fail-safe 默认档；
- **审计入口**：approval log 查询（谁 / 何时 / 哪条规则 / 决议）。

### 4.6 存储与热生效

- 规则落 DB 表 `approval_policy_rule(id, scope, tool_pattern, arg_pattern, tier, priority, source, updated_by, updated_ts)`；toml 作为 bootstrap seed 首次导入；
- 热生效不重启：表带 version stamp，`classify` 每次评估比对 stamp（内存缓存 + 失效重建，成本一次整数比较）；
- 多实例部署：stamp 走 DB 天然一致；P2 换 redis pub/sub 推送。

### 4.7 UI 护栏

- 托管 / 内置 deny 锁定（只可加严不可放松）；
- 每次保存写审计（diff 形式：旧档→新档、修改人、时间戳）；
- P2 **shadow 模式**：新规则先 observe-only 跑 N 天，只记「本会拦截 / 本会放行」不真拦，企业策略上线前的标准动作。

---

## 5. ApprovalCenter（确认生命周期）

### 5.1 注册 / 等待 / 决议

```python
approval = center.register(tool, args, ctx)      # → approval_id + asyncio.Event
# ctx: conv_id / engine / stream_callback（经 contextvar 注入，见 §6）
push SSE approval.requested {approval_id, conv_id, tool, args_preview, risk, ts}
if intent_analysis: 异步 LLM 一句话 → push approval.intent {approval_id, intent}
decision = await approval.event.wait(ttl)        # timeout → decision=timeout
# resolve 由 REST 端点触发：
center.resolve(approval_id, decision, scope, reason)
push SSE approval.resolved {approval_id, decision, scope, ts}
```

### 5.2 决议回灌（observation 模板）

- **reject**：`[approval] 用户拒绝了本次 {tool} 调用（原因：{reason or '未说明'}）。不要重试同一操作；如目标仍需达成，改用只读或更低风险的方式，并向用户说明。`
- **timeout**：同 reject，原因标注「确认超时（{ttl}s）」。
- **deny**：`[policy] {tool} 被安全策略拦截（规则：{rule_id}）：{hint}。改用替代方案或向用户说明为何不可行。`

### 5.3 记忆（scope）

- **once**：仅本次生效；server 签发单次 `approval_token`（绑定 approval_id + tool + args hash），执行端带 token 跳过 gate。
- **session**：conv 级 pattern 白名单（内存 + conv meta 持久化）；后续同 tool + 同 args hash 自动通过。
- **always**：写入 toml `[service.approval.rules]`（用户可编辑）或 DB 用户级规则表（P1）。

### 5.4 审计

表 `tool_approval_log(approval_id, conv_id, engine, tool, args_hash, risk, intent, decision, scope, ts)`（P1）。

---

## 6. dbgpt 引擎接入（gate 插入）

### 6.1 插入点

`ToolAction.run_tool`（`packages/dbgpt-core/src/dbgpt/agent/expand/actions/tool_action.py:162`）→ `:226 async_execute` **之前**：

```python
verdict = policy.classify(tool_name, args)
if verdict.level == "deny":
    return policy_observation(verdict)                 # §5.2
if verdict.level == "confirm" and not token_valid(args):
    approval = center.register(tool_name, args, ctx)
    decision = await approval.wait(ttl)
    if decision != "approve":
        return rejection_observation(decision)         # §5.2
    token = center.issue_token(approval)               # once 记忆
# 继续 async_execute
```

### 6.2 ctx 注入（contextvar）

`current_approval_ctx` 由 agent_runner / `agentic_data_api` 在 turn 开始时 set（携带 conv_id + stream_callback）；`tool_action` 读取；缺失时 gate 禁用（单测 / 其他调用方不受影响）。

### 6.3 并行 tool_calls（run_tools_batch :312 / gather :377）

并发执行前**先批量注册**所有 confirm 调用（同一 tick 内 push 多张确认卡，前端堆叠），再 `asyncio.gather` 并发等待 + 执行。

### 6.4 SSE 事件转发

`agentic_data_api.py:3704` 附近事件白名单新增 `approval.requested / approval.intent / approval.resolved`。

---

## 7. pi 引擎接入（HTTP 202 + 轮询 + token 兑换）

### 7.1 为什么走 202 而不是长连接

pi 侧工具调用超时不确定（extension fetch 无显式 timeout，pi 内部 tool timeout 未知）；长连接等待确认（可能 300s）有被 pi 侧掐断的风险。**202 + 轮询 + token 兑换**复用 question 已验证的范式，规避该不确定性。

### 7.2 服务端（run_harness_tool handler :318，:371 直通执行之前）

```python
verdict = policy.classify(tool_name, args)
if verdict.level == "confirm" and not token_valid(args):
    approval = center.register(tool_name, args, ctx)
    push_conv_event(approval.requested)                # :1316-1321 旁路
    return JSONResponse(202, {"approval_id": approval.id, "poll_url": ...})
# 带有效 token → 跳过 gate；auto → 直接执行
```

### 7.3 extension 侧（dbgpt_tools.ts 通用路径）

```ts
const res = await fetch(runUrl, {...});
if (res.status === 202) {
  const { approval_id } = await res.json();
  const decision = await pollApproval(approval_id);    // 2s 间隔 / 320s deadline（对齐 question）
  if (decision.status !== "approved") return rejectionObservation(decision);
  const exec = await fetch(runUrl, { headers: { "X-Approval-Token": decision.token }, ... });
  return exec.json();
}
```

### 7.4 原生工具策略

bash / edit / write 等保留在 pi 侧（`_CORE_TOOLS`）；shell 类需走桥接 `shell_interpreter` 才自然进入 gate。pi 升级 hook（在 pi 侧原生工具执行前回调 gate）列为 P2 评估项。

---

## 8. 前端悬浮层：确认卡与 question 卡

### 8.1 形态：悬浮 dock（composer 上方）

approval 与 question 两类卡**均不进 timeline**，统一悬浮渲染在 composer（输入框）上方：
- 位置：紧贴 composer 上沿（6px），居中与 stream 同宽（max 780px）；阴影强于时间线卡以表达层级；高度不足时内部滚动（max-height 60vh）；无全屏遮罩，dock 外区域仍可滚动回看上下文。
- 多张 pending 叠放顺序：**approval（安全语义）> question（信息收集）**，间距 10px；决议后 200ms fade-out 消隐。
- approval 卡四要素：红色渐变头部（高危标记 + 工具名 + 规则 chip）、参数预览代码块、意图说明行（spinner → `approval.intent`）、按钮组（拒绝 / 允许 + scope 下拉 once/session/always）。
- 全局状态行：流尾「等待你的确认…」/「等待你的回复…」；决议后切换为「已允许 / 已拒绝 / 已超时」。

### 8.2 时间线接入（紧凑审计行）

timeline 不再插大卡：`AgentTimeline.tsx` 为每个 approval 增加一条紧凑行（工具行 + 状态 chip：待确认 / 已允许·scope / 已拒绝 / 超时·自动拒绝 / 策略拦截），rejected/timeout/denied 于行下附 observation 引用行；并行多 approval 按发起顺序多行。question 行复用现有 question step 行 + chip（待回复 / 已回复 / 已跳过）。历史回放直接以 resolved 态渲染行。

### 8.3 SSE / REST

- 解析白名单（`react-sse-parser.ts:175`）新增三个事件。
- 决议：`POST /api/v1/chat/approval/{id}/resolve` body `{decision, scope, reason?}`。
- 刷新恢复：`GET /api/v1/chat/approval/pending?con_uid=` 返回待确认卡列表。

### 8.4 历史回放

approval / question 的决议状态随 step meta 持久化；回放时 timeline 审计行直接呈现最终态（已允许 / 已拒绝 / 已超时 / 已回复 / 已跳过），dock 不重现待确认卡。

### 8.5 question 卡重设计（对齐 AskUserQuestion 形态）与语义分离

QuestionDock 按截图形态重设计并并入悬浮层：
- 编号选项（1/2/3…）+ 内联灰描述，选中项编号反色 + 行白底；
- 「… Other（请填写）」自由输入行；
- 多题分页：头部右侧 `1 / 2` + 左右箭头；`下一题 ↵` 在当前页选中后可用（Enter 快捷），末题即提交；
- 底部左 `推荐` = 一键选中策略推荐项；底部右 `跳过` = 走 question.rejected。
语义边界保留：question = 收集信息，approval = 授权执行；两者不混组件，仅共用悬浮层容器与叠放规则。

---

## 9. 分期

| 期 | 内容 |
|---|---|
| **P0** | ToolRiskPolicy 规则表 + toml 扩展；dbgpt 引擎 gate（tool_action :162 前）；ApprovalCenter 注册/等待/决议；确认卡 + SSE 三事件 + 决议 API + 刷新恢复；session 记忆；reject/timeout/deny observation 回灌 |
| **P1** | pi 引擎 202 流程（服务端 + extension）；意图分析（approval.intent）；always 记忆（toml 写入）；审计表 tool_approval_log；setting 页（工具档位表 + 规则编辑器 + 试运行框 + 白名单管理，§4.5） |
| **P2** | shell/code 沙箱兜底（执行层 floor）；SQL 写操作 confirm 档细化；pi 原生工具 hook；多实例 redis 化（in-memory Event → redis pub/sub）；shadow 模式 + 托管锁（§4.7） |

---

## 10. 测试计划

- **单测**：规则表参数化（auto/confirm/deny 三档 × 参数模式匹配 × toml 覆盖）。
- **集成**：`curl -sN` 触发 react-agent 执行 `shell_interpreter` 高危命令 → 收到 `approval.requested`；resolve approve → 工具执行；resolve reject → observation 含拒绝文案；ttl 超时 → 自动 reject。
- **pi e2e**：extension 202 → 轮询 → token 兑换 → 执行；reject → rejection observation 回灌 pi。
- **前端**：确认卡状态机（intent 分析中 / 待确认 / 已允许 / 已拒绝 / 已超时）；刷新恢复待确认卡；历史回放最终态。

---

## 11. 风险与边界

- **确认疲劳**：session 记忆 + 低风险默认 auto + 意图说明行缓解；always 档仅调试用。
- **并行多卡顺序**：按发起顺序堆叠；批量决议（v2）。
- **SSE 断连 ≠ 确认丢失**：确认状态在服务端（ApprovalCenter），刷新经 pending API 恢复。
- **多实例**：in-memory asyncio.Event 限单实例；P2 redis pub/sub。
- **IM / channel 侧**：channel 无确认卡 UI，policy 降级为 deny + 通知（P2）。
- **审计合规**：P1 审计表落盘。

---

## 12. 参考（一手文档）

- Claude Code permissions：`permissions.allow/ask/deny` 三表 + 确认卡四要素 + 记忆下拉。
- OpenAI Agents SDK：`function_tool(needs_approval=...)` + `ToolApprovalInterrupt` + approve/reject 回灌。
- LangGraph：`interrupt(payload)` + `Command(resume=decision)` + human-in-the-loop middleware + checkpoint 持久化。
- MCP elicitation：`elicitation/create` + accept/decline/cancel + 决议回灌协议语义。
- Microsoft Agent Framework：`@tool(approval_mode=...)` + 确认卡 + 审计表。
