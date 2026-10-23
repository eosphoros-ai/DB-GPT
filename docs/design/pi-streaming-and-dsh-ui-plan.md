# pi 引擎流式输出修复 + DSH 风格交互改进方案

> 日期：2026-10-14　关联：`harness-engine-switch-plan.md`、`pi harness 实现`（[pi-harness-impl]）
> 目标：① 修复 pi 引擎下"不流式"（只有 final 没有中间步骤推进）的问题；② 参考 deepseek-harness 的交互形态（左侧 Task 导航树 + 右侧步骤展开）优化 DB-GPT 首页的 agent 运行体验。

---

## 1. 现状诊断：pi 引擎为什么"不流式"

### 1.1 事件流对比

DSH 的 trajectory 是**逐事件、可滚动的时间线**（ledger），DSH 主机事件类型（从 `packages/client/ui-trajectory/` 反推）：

```
turn_start → assistant/chunk（逐 token）→ tool-call → tool result → turn_end
compaction_start / compaction_end
step/end
```

而 pi 引擎的现状（代码：`harness_pi_stream.py` 的 `_translate_event`）：

| pi 事件（RPC） | 现状翻译 | 是否流式展示 |
|---|---|---|
| `thinking_delta`（text_delta/thinking_delta） | 只累加进 `state.thought_buffer`，**不发 SSE 帧** | ❌ 用户看不到 |
| `tool_execution_start` | `step.start` + `step.meta` | ✅ 有 |
| `tool_execution_update`（partialResult） | `step.chunk` | ✅ 有（但工具流不常有） |
| `tool_execution_end` | `step.chunk` + `step.done` | ✅ 有 |
| `message_end`（assistant） | 只进 `state.final_text`，不发帧 | ❌ 用户看不到 |
| `agent_settled` | 只标记 done | ❌ 无 UI 反馈 |

**结论**：问题不在"不流式"——**我们根本没把 thinking 流式事件发给前端**（翻译层只累积不发）。中间步骤卡（tool 的）是有的，但纯问答轮（无工具）就是 30 秒静悄悄然后一个 final。

### 1.2 为什么 DSH 感觉"流式"

DSH 的 trajectory 核心是把 **assistant/chunk** 当作一等公民渲染（每 token 一次 cell 更新），即使是 thinking 也有 dedicated reasoning 块展示。DB-GPT 的 ManusLeftPanel 有 `step.chunk` 通道，我们只需要把 pi 的 delta 映射到它。

---

## 2. 修复 1：pi 引擎流式 thinking（小改动、立即生效）

### 2.1 方案

把 pi 的 `thinking_delta` / `text_delta` 直接映射为 `step.chunk`（前端已有消费通道），并保证同一个 turn 内的所有 delta 落到**同一个 step**（thought-only step）：

| pi 事件 | 映射 | SSE 帧 |
|---|---|---|
| `turn_start` | 开始新 thought step（pending） | `step.start{title:"思考中"}` |
| `thinking_delta` / `text_delta` | 增量 chunk | `step.chunk{output_type:"text", content:delta}` |
| `message_end`（assistant） | 结束 thought step | `step.done` + thought 进 `step.meta` |
| 有工具调用 | thought step 结束于 tool 开始时 | 现有逻辑 |

### 2.2 具体实现

修改 `harness_pi_stream.py` 的 `_translate_event`：

```python
# 新增：thought-only step 生命周期管理
class _PiSessionState:
    thought_step: Optional[Dict[str, Any]] = None  # 当前思考 step 记录
    thought_content: str = ""                       # 累积文本（step.meta 用）

def _translate_event(state, ev):
    if kind == TURN_START:
        # 若有悬挂 thought step 先 close（防御）
        ...
        # 创建 thought step（pending，不 yield step.start——等有内容再发）
        state.thought_step = state.build_step("思考中", "pi agent thinking")
        state.thought_content = ""
        return []

    if kind in (THINKING_DELTA,):
        if state.thought_step is None:
            return []
        # 首次有内容才发 step.start
        frames = []
        if not state.thought_content:
            frames.append(_sse_event({"type": "step.start", ...}))
        state.thought_content += ev.text
        # 增量 chunk 推给前端（前端 ManusLeftPanel 会累加显示）
        frames.append(_sse_event({
            "type": "step.chunk",
            "id": state.thought_step["id"],
            "output_type": "text",
            "content": ev.text,
        }))
        return frames

    if kind == TOOL_START:
        # 结束 thought step（发 step.done），然后走现有 tool step 逻辑
        frames = []
        if state.thought_step and state.thought_content:
            frames.append(_sse_event({"type": "step.done", "id": ..., "status": "done"}))
            state.thought_step = None
        frames.extend(_existing_tool_start(...))
        return frames

    if kind == MESSAGE_END:
        # 关闭 thought step；final_text 照常
        ...
```

前端**零改动**（ManusLeftPanel 已经会渲染 `step.chunk` 的 text 内容）。

### 2.3 验证

- 单测：`test_thinking_delta_streaming`（连续 3 个 delta → 3 个 step.chunk 帧）
- e2e：首页发 `hi`，应看到左侧 Execution Steps 实时出现「思考中」卡片逐字生长

---

## 3. 方案 2：DSH 风格的交互形态（中长期、独立文档）

DSH 的 UI 是**三层结构**（从 `packages/client/ui-trajectory` + `ui-layout` + `ui-sidebar` 反推）：

```
┌─────────────────────────────────────────────────────────────┐
│ Header（workspace / session / model）                        │
├──────────┬──────────────────────────────────────────────────┤
│ Sidebar  │ Conversation / Trajectory                        │
│ (tree:   │                                                  │
│  - Goal  │  ┌─ User (bubble)                                │
│  - Turn1 │  ├─ Assistant (cell: reasoning + text + tool)    │
│  - Turn2 │  │   ├─ Tool call tree (展开 input/output)       │
│  - ...   │  └─ Turn divider                                 │
│  - Tools │                                                  │
│  - Jobs  │  ┌─ Turn 2 ...                                   │
│  - SubAg │                                                  │
└──────────┴──────────────────────────────────────────────────┘
│ Composer（底部，浮动）                                        │
└─────────────────────────────────────────────────────────────┘
```

核心特征（与 DB-GPT 当前 ManusLeftPanel 的差异）：

| DSH | DB-GPT 当前 | 差距 |
|---|---|---|
| **时间线 ledger**（左树 Turn/Step 分组，主区横向时间轴） | 垂直步骤卡列表（Execution Steps） | 时间感弱，多轮任务难导航 |
| **thinking 有独立 reasoning 块**（可折叠） | thought 塞进 step.meta（看不到） | 已经通过方案 2 部分解决 |
| **Tool call 有独立 tree**（input/output 展开） | step.chunk 平铺 | 复杂工具调用阅读费劲 |
| **Overview 时间轴**（顶部一条横向甘特图） | 无 | 长任务进度感差 |

### 3.1 分期建议

**P0（立即，本周）**：只解决"pi 引擎不流式"（方案 2），前端零改动。
**P1（下周）**：在现有 ManusLeftPanel 基础上做"DSH 化"增强（不改架构）：
- 每个 step 卡**可折叠**：默认折叠 thinking 部分，展开看完整
- step 卡内 **tool input/output 分离展示**（参考 DSH 的 TrajectoryCell）
- 底部 composer 上方加一条**执行时间轴**（窄条、显示 turn 边界）
**P2（以后）**：如果 DSH 的交互深度被验证值得引入，再评估是否引入 DSH 的 web UI 组件（`@deepseek-ai/dsh-client-web`）或重构成类似结构。

### 3.2 技术选型

- P0/P1 用现有 React + ManusLeftPanel（Ant Design + Tailwind），不引入新框架
- 若 P2 要引入 DSH UI：DSH 是 React + TypeScript + Vite，其 `client-web` 是独立 npm 包，可考虑嵌入 iframe 或 fork 其 trajectory 组件（Apache 2.0 License 兼容）

---

## 4. 优先级与落地顺序

1. **今天就做**：方案 2（pi 流式 thinking）——代码改动小、用户感知强，是"pi 能用"到"pi 好用"的关键一步
2. **本周内**：P1 的 step 卡折叠 + tool input/output 分离——改善任何引擎的复杂任务阅读体验
3. **下周起**：P2 的 DSH UI 深度评估——独立设计文档，不阻塞 pi 引擎落地

---

## 5. 待确认问题

1. **DSM（deepseek-v4-flash）的工具调用协议**——现在输出 DSML 文本块，pi 识别不了，用户在 DB-GPT 场景下用 deepseek 模型会持续输出不可解析的工具调用文本。是否要在 pi 的模型层加 DSML → tool_calls 的适配？（独立 issue）
2. **P1 的 UI 改进**是否要全引擎统一（pi 和 dbgpt 引擎同样的 step 卡形态）——建议统一，前端不感知引擎
3. **DSH web UI 的 License**——Apache 2.0（Apache License, Version 2.0），可安全引用/链接/fork
