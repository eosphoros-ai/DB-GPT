# 扩展 Harness：新增一个引擎

引擎是 DB-GPT 产品契约（SSE 流、工具、审批、产物、历史）与某个外部/内部 Agent 运行时之间的
适配器。pi 适配器（`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/harness_pi_stream.py`）是
参考实现；Codex、DSH 一类引擎遵循同样的六个接缝。

## 契约总览

| 接缝 | 产品层期望 | pi 参考实现 |
|---|---|---|
| 身份与可用性 | 引擎 id 进 `KNOWN_ENGINES`；`engine_availability()` 提供探测项（`name`/`available`/`detail`） | `_probe_pi_cli()`（CLI + Node ≥ 22.19） |
| 选择 | 遵循 `ext_info.harness_engine` → 服务端偏好 → 项目默认；自动出现在 Setting 弹层 | `resolve_harness_engine()` |
| 流 | 前端解析的 SSE 事件（见下） | pi rpc 帧 → step 事件 |
| 工具 | 受控工具带 + 审批门 + 只读 containment | `tool_bridge.register_conv_tools()` + `/v1/chat/harness/tool/run` |
| 产物 | envelope chunk 无截断提升（html / image / query），文件走 artifact-file 端点 | `_embedded_artifact_outputs()` |
| 历史 | protocol-v2 payload（steps + outputs），刷新重建轨迹与产物 | storage conversation 写入 |

## 第 1 步——注册引擎

把 id 加入 `KNOWN_ENGINES`，并在 `engine_availability()` 增加探测项。探测按请求执行，因此
安装引擎 CLI 不应需要重启服务。Setting 弹层、偏好端点与快速失败门控都只从这两处派生——
UI 其余部分无需改动。

## 第 2 步——解析与门控

复用 `resolve_harness_engine()` 式解析。若新引擎要成为新部署的项目默认，遵循
`_default_harness_engine()` 的可用性门控模式：仅当探测成功才默认新引擎，否则回落 `dbgpt`。
显式请求的引擎不可用时，务必在任何 Agent 工作开始前以终止流消息快速失败。

## 第 3 步——流适配器

发射前端已解析的 SSE 契约，其余一律会被静默丢弃：

- `step.start` / `step.meta`（thought、action、action_input、intention）/ `step.done`
- `step.chunk`，`output_type` 取 `thought | text | markdown | code | html | image | file |
  query | table`
- 人机协同帧：`approval.requested` / `approval.resolved` / `approval.intent`、
  `question.asked` / `question.replied` / `question.rejected`
- 终止的 protocol-v2 payload：持久化 steps 与 outputs 供历史回放

工具结果以 `{"chunks": [{"output_type": ..., "content": ...}]}` envelope 传输；展示文本对
模型/UI 做截断，但产物 payload 必须无截断提升（见第 5 步）。

## 第 4 步——桥接工具

两种方案，按优先级：

1. **HTTP tool-run 桥（pi 模式）**：在服务端注册会话工具包，向引擎下发工具名 + JSON schema
   清单，调用经内部 token 保护端点执行。审批门位于该端点，所有引擎免费继承策略、deny/confirm
   分级与 session/always 记忆。
2. **原生 function-calling**：引擎若支持 OpenAI 风格 tools，将同一工具包序列化为 schema，
   且每次调用执行前过同一审批门。

containment 规则保持引擎无关：只读 SQL、沙箱化代码/Shell、默认排除破坏性内置工具。

## 第 5 步——提升产物

工具 envelope 携带 `html` / `image` / `query` chunk 时，将其**无截断**提升为类型化流输出
（pi 适配器的 `_embedded_artifact_outputs`），并写入 step outputs。会话工作区落盘的文件产物
经受限 artifact-file 端点呈现；不要把二进制内联进流。

## 第 6 步——持久化历史与轨迹

写入 protocol-v2 回合 payload（含 outputs 的 steps、引用、final content），使刷新页面能重建
时间线与产物卡。引擎若自带 trace，合成 Trace 视图可渲染的 span（根 + 每动作），参考
`_write_pi_trace`。

## 骨架：Codex 风格适配器

```python
KNOWN_ENGINES = ("dbgpt", "pi", "dsh", "codex")

def _probe_codex() -> tuple[bool, str]:
    path = shutil.which("codex")
    return (True, path) if path else (False, "codex CLI not found")

async def stream_codex_turn(dialogue) -> AsyncIterator[str]:
    engine = resolve_harness_engine(dialogue)
    if engine == "codex" and not _probe_codex()[0]:
        yield terminal_message("engine codex unavailable")  # 快速失败
        return
    conv = open_storage_conversation(dialogue)
    manifest = tool_bridge.register_conv_tools(dialogue.conv_uid, dialogue.ext_info, app)
    async for frame in codex_client.run(prompt=dialogue.user_input, tools=manifest):
        for event in translate_to_sse_contract(frame):   # step.* / approval.* / chunks
            yield sse(event)
        for artifact in promote_envelope_chunks(frame):  # html / image / query，无截断
            yield sse(artifact)
    persist_protocol_v2(conv, steps, outputs, final_content)
```

## 检查清单

- [ ] id 进 `KNOWN_ENGINES`，探测进 `engine_availability()`（装 CLI 免重启）
- [ ] 遵循解析顺序；显式不可用选择快速失败
- [ ] 发射 SSE 契约；未知事件类型绝不泄漏到客户端
- [ ] 工具过审批门桥接；containment 与 dbgpt/pi 对齐
- [ ] html / image / query 产物无截断提升并持久化
- [ ] 写入 protocol-v2 历史；引擎有 trace 时合成 span
- [ ] 探测与解析单测（参考 `tests/test_harness_engine_default.py`）
- [ ] SSE 端到端捕获，断言 `step.chunk output_type=query` 一类 payload
