# DB-GPT Agent Harness 整体设计方案

> 整理日期：2026-04-25（更新：2026-04-25 增加操作快照文件机制）
> 代码分支：test_v0.8.0

---

## 一、整体架构概览

DB-GPT 的 Agent 系统以 **ConversableAgent** 为核心，基于四模块设计（Profiling / Memory / Planning / Action），实现具备推理和执行能力的自主 Agent。

```
┌─────────────────────────────────────────────────────────────┐
│                        User Request                         │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│               Controller (controller.py)                    │
│  - 创建 GptsConversation 记录 (status: RUNNING)             │
│  - 初始化 AgentMemory (HybridMemory)                        │
│  - 初始化 GptsMemory (对话历史)                             │
│  - 调用 agent_team_chat_new()                               │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│        ConversableAgent.initiate_chat()  (base_agent.py)    │
│  - 创建 AgentMessage (content, goal, context)               │
│  - 调用 send() → 触发 receive()                             │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│              generate_reply() 主执行循环                     │
│           [Think → Review → Act → Verify] × N               │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心类层次结构

```
Agent (agent.py) — 抽象接口
  └── Role (role.py) — 角色 + 记忆 + Prompt 模板
        └── ConversableAgent (base_agent.py) — 完整实现
              └── ReActAgent (react_agent.py) — ReAct 推理模式
```

**关键接口**（`agent.py`）：

| 方法 | 说明 |
|---|---|
| `send()` / `receive()` | 消息路由 |
| `thinking()` | LLM 推理 |
| `review()` | 内容审核 |
| `act()` | 动作执行 |
| `verify()` | 结果验证 |

---

## 三、完整执行流程

### 3.1 Agent 生命周期

```
bind()                          → 绑定配置 (LLM / Memory / Resource / Action)
  ↓
build()                         → 初始化 LLM、恢复历史记忆
  ↓
initiate_chat(recipient, msg)   → 发起对话
  ↓
receive(message, sender)        → 接收消息
  ↓  _a_process_received_message() → 写入 Memory
  ↓
generate_reply()                → 主执行循环
```

### 3.2 `generate_reply()` 主循环（`base_agent.py:436-736`）

```
每一轮 retry 循环：
┌──────────────────────────────────────────────────────┐
│  Stage 1: THINKING                                   │
│    _load_thinking_messages()                         │
│      ├─ 系统 Prompt（含 task_progress）              │
│      ├─ 历史 Memory                                  │
│      └─ 当前 Observation / Question                 │
│    → [上下文管理] manage_context() 介入              │
│    → thinking() 调用 LLM                            │
│    → 支持 stream_callback 流式输出                   │
├──────────────────────────────────────────────────────┤
│  Stage 2: REVIEW                                     │
│    review(llm_reply) → approve / comments           │
├──────────────────────────────────────────────────────┤
│  Stage 3: ACT                                        │
│    act(reply_message) → ActionOutput                │
│    解析 LLM 输出 → 按顺序执行所有注册 Action         │
├──────────────────────────────────────────────────────┤
│  Stage 4: VERIFY                                     │
│    verify(reply_message) → check_pass / reason      │
│    ✅ 成功 → write_memories() → 返回结果             │
│    ❌ 失败 → 更新 observation → retry               │
└──────────────────────────────────────────────────────┘

失败时：retry_counter++ → 回到 Stage 1（最多 max_retry_count 次）
```

**`write_memories()` 更新 task_progress**（`role.py`）：

```python
if check_pass and action:
    snapshot_path = self._write_op_snapshot(step, action, action_input, observation, thought, phase)
    _task_progress.append({
        "step": step_num,
        "action": action,
        "phase": phase,
        "status": "done",
        "observation_tokens": obs_tokens,
        "snapshot_file": snapshot_path or "",   # ← 快照文件路径
    })
```

### 3.3 bind() 绑定系统

`ConversableAgent.bind()` 支持多类型绑定，按传入类型自动路由：

```python
agent.bind(LLMConfig)       # 配置 LLM
agent.bind(AgentContext)    # 设置运行时上下文
agent.bind(Resource)        # 挂载工具/资源
agent.bind(AgentMemory)     # 设置记忆系统
agent.bind(ProfileConfig)   # 设置角色 Profile
agent.bind(Skill)           # 挂载技能（含 Prompt）
agent.bind(Action)          # 注册可执行 Action
agent.bind(PromptTemplate)  # 覆盖 Prompt 模板
```

### 3.4 AgentMessage 数据结构

```python
@dataclass
class AgentMessage:
    content: Optional[str]                 # 主响应文本
    name: Optional[str]                    # 发送方名称
    role: Optional[str]                    # Agent 角色
    rounds: int                            # 对话轮次
    context: Optional[Dict]               # 动态上下文变量
    current_goal: Optional[str]           # 当前任务目标
    model_name: Optional[str]             # 使用的 LLM 模型
    action_report: Optional[ActionOutput] # 工具执行结果
    review_info: Optional[AgentReviewInfo]# 审核决策
    success: bool                         # 整体成功标志
    resource_info: Optional[Dict]         # 工具引用信息
```

---

## 四、上下文管理系统

位于 `packages/dbgpt-core/src/dbgpt/agent/core/context/`

### 4.1 整体架构

```
┌────────────────────────────────────────────────────────────────┐
│                     ContextManager (manager.py)                │
│                                                                │
│   ContextBudgetTracker ──→ Token 计数 + TokenState 判断        │
│          │                                                     │
│          ↓                                                     │
│   ┌──────────────────────────────────────────────────────┐    │
│   │           四层渐进式压缩策略 (compact.py)             │    │
│   │  Layer 1: ObservationMicroCompact  (轻量截断)         │    │
│   │  Layer 2: SessionMemoryCompact     (无 LLM 开销)      │    │
│   │  Layer 3: FullContextCompression   (LLM 摘要)         │    │
│   │  Layer 4: ReactiveCompact          (紧急兜底)          │    │
│   └──────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 Token 预算配置（`budget.py`）

```python
class ContextBudgetConfig:
    max_context_tokens: int = 120_000       # 总预算
    reserved_tokens: int = 4_096            # 预留输出空间
    # → effective_budget = 116,000

    warning_threshold: float = 0.70         # 触发 Layer 1/2
    error_threshold: float = 0.90           # 触发 Layer 3
    critical_threshold: float = 0.95        # 标记 CRITICAL 状态

    min_keep_recent_rounds: int = 3         # 最少保留最近 N 轮
    max_observation_age_rounds: int = 5     # Observation 截断阈值
    truncated_observation_max_chars: int = 200
    min_keep_tokens: int = 10_000           # 压缩后最低保留量
```

**TokenState 状态机：**

```
Token 使用率:   0% ─────── 70% ─────── 90% ─────── 95% ─────── 100%
TokenState:    NORMAL     WARNING      ERROR      CRITICAL
```

### 4.3 四层压缩策略详解

#### Layer 1：ObservationMicroCompact（轻量截断）

- **触发条件**：TokenState >= WARNING（70%），且消息是 5 轮前的 Observation
- **策略**：将旧 Observation 内容截断至 200 字符
  - 若消息 `context["snapshot_path"]` 存在，截断提示携带文件路径：`[truncated, full detail at: step_001_execute_python.json]`
  - 否则提示：`[truncated]`
- **特点**：无 LLM 调用，执行极快；通过快照文件索引保留完整结果可达性

#### Layer 2：SessionMemoryCompact（丢弃旧轮次）

- **触发条件**：TokenState >= WARNING（70%）
- **策略**：
  - 识别 ReAct 三元组边界（Thought / Action / Observation）
  - 保留最近 `min_keep_recent_rounds` 完整轮次
  - 确保剩余 Token ≥ `min_keep_tokens`
- **关键设计**：task_progress 已注入 System Prompt（含每步的快照文件名），丢弃旧轮次后 Agent 可按需 `read_file(snapshot_path)` 恢复精确数据

#### Layer 3：FullContextCompression（LLM 摘要压缩）

- **触发条件**：TokenState >= ERROR（90%）且 llm_client 可用
- **策略**：调用一次 LLM 生成结构化摘要，替换旧消息

  摘要结构：
  ```
  1. 原始任务
  2. 已完成步骤
  3. 当前状态
  4. 关键数据（文件名、路径等精确值）
  5. 遇到的错误
  6. 下一步计划
  ```

- **特点**：一次额外 LLM 调用，可释放大量上下文空间

#### Layer 4：ReactiveCompact（紧急兜底）

- **触发条件**：LLM 返回 `context_too_long` / `context_length_exceeded` 错误
- **策略**：仅保留 System Prompt + 最近 2 轮（最小可运行状态）
- **调用位置**：`base_agent.py` 的 `except LLMChatError` 块

```python
except LLMChatError as e:
    if _ctx_mgr and "context_too_long" in err_str:
        thinking_messages = await _ctx_mgr.reactive_compact(thinking_messages)
        llm_reply = await self.thinking(...)  # 重试
```

### 4.4 上下文管理完整流程

```
_load_thinking_messages() 组装消息列表
        ↓
ContextManager.manage_context(messages, round, task_progress)
        ↓
  ┌─────────────────────────────────────────────────┐
  │  Step 1: 计算 Token 数                          │
  │    ProxyTokenizerWrapper 精确计数               │
  │    失败时 fallback: len(content) / 4            │
  ├─────────────────────────────────────────────────┤
  │  Step 2: 判断 TokenState                        │
  │    推送 context.status 事件到前端（SSE）         │
  ├─────────────────────────────────────────────────┤
  │  Step 3: if state >= WARNING                    │
  │    apply Layer 1（Observation 截断）             │
  │    apply Layer 2（丢弃旧轮次）                   │
  ├─────────────────────────────────────────────────┤
  │  Step 4: if state >= ERROR and llm_client       │
  │    apply Layer 3（LLM 摘要压缩）                │
  └─────────────────────────────────────────────────┘
        ↓
返回压缩后的 messages → 送入 LLM
        ↓
  如果 LLM 报 context_too_long 错误
        ↓
ContextManager.reactive_compact()  ← Layer 4
        ↓
重试 LLM 调用
```

### 4.5 task_progress 持久化机制

**核心设计**：task_progress 存储在 Role 实例的普通 Python 属性 `_task_progress: List[Dict]`（非 Pydantic 字段），因此：

- 不随上下文消息一起被压缩策略丢弃
- 每轮 System Prompt 自动注入当前进度摘要（含快照文件名）
- 防止 Agent 在上下文压缩后**重复执行已完成步骤**

注入示例：

```
## Task Progress (do NOT repeat completed steps)
✅ Step 1: Action=execute_python | Phase: 数据加载    | ref: step_001_execute_python.json
✅ Step 2: Action=write_file     | Phase: 保存结果    | ref: step_002_write_file.json
✅ Step 3: Action=execute_python | Phase: 生成图表    | ref: step_003_execute_python.json
```

**更新时机**：每次 `verify()` 通过后，在 `write_memories()` 中追加，同时写入快照文件。

### 4.6 操作快照文件机制

**设计背景**：Layer 1 截断和 Layer 2 丢弃旧轮次后，上下文里的 Observation 内容（工具返回的精确值、文件路径、计算结果）会永久丢失，向量 Memory 的语义检索也不能保证精确召回。为此引入操作快照文件，将完整内容卸载到磁盘，上下文只保留引用。

**文件结构**：

```
{output_dir}/{conv_id}/
  ├── step_001_execute_python.json
  ├── step_002_write_file.json
  └── step_003_execute_python.json
```

- `output_dir` 来自 `AgentContext.output_dir`；未设置时 fallback 到 `DBGPT_HOME/workspace/op_snapshots`
- 文件名格式：`step_{step:03d}_{action_name}.json`，按步骤编号可排序

**快照文件内容**：

```json
{
  "step": 1,
  "action": "execute_python",
  "phase": "数据加载",
  "thought": "需要先了解数据结构",
  "action_input": "df = pd.read_csv('sales.csv')\nprint(df.shape)",
  "observation": "执行成功：(1000, 12)\n列名: date, region, amount...",
  "timestamp": "2026-04-25T10:30:00",
  "conv_id": "abc123"
}
```

**三处集成点**：

| 位置 | 行为 |
|---|---|
| `role.py: write_memories()` | Action 成功后调用 `_write_op_snapshot()`，路径存入 `fragment.snapshot_path` 和 `_task_progress` |
| `compact.py: Layer 1` | 截断 Observation 时从 `msg.context["snapshot_path"]` 取路径，注入到截断提示 |
| `react_agent.py: read_memories()` | 从 Memory 检索到 fragment 时，若有 `snapshot_path`，在重建的 Observation 消息末尾追加提示 |

**恢复流程**：

```
Agent 需要早期步骤的精确结果
        ↓
task_progress 中看到 ref: step_001_execute_python.json
        ↓  或  Memory 检索到的消息末尾有提示
        ↓
Agent 主动调用 read_file(snapshot_path)
        ↓
拿回完整 action_input + observation，无信息损失
```

**与向量 Memory 的关系**：快照文件是精确引用，向量 Memory 是语义检索，两者互补：
- 向量 Memory 适合模糊回忆（"之前做过什么"）
- 快照文件适合精确还原（"第 3 步的具体输出是什么"）

### 4.7 上下文管理初始化

**`AgentContext` 配置参数**（`agent.py`）：

```python
@dataclass
class AgentContext:
    conv_id: str
    output_dir: Optional[str] = None       # 快照文件写入目录

    # 上下文管理开关
    enable_context_management: bool = False
    max_context_tokens: int = 120000
    context_warning_threshold: float = 0.70
    context_error_threshold: float = 0.90
```

**ReActAgent 自动启用**（`react_agent.py`）：

```python
if (
    self.agent_context is not None
    and self.agent_context.enable_context_management
):
    self.init_context_management()
```

---

## 五、流式输出事件（SSE）

上下文管理与执行过程通过 SSE 向前端实时推送事件：

| 事件类型 | 触发时机 | Payload |
|---|---|---|
| `thinking_chunk` | LLM token 流式输出 | 增量文本 |
| `thinking` | LLM 推理完成 | 完整回复 |
| `act` | Action 执行结果 | ActionOutput |
| `context.status` | Token 状态变化 | `{used, budget, ratio, state, compact_layer}` |
| `[DONE]` | 对话完成 | — |

**`context.status` Payload 示例**：

```json
{
  "type": "context.status",
  "used": 85000,
  "budget": 116000,
  "ratio": 0.73,
  "state": "WARNING",
  "compact_layer": "SessionMemoryCompact"
}
```

---

## 六、记忆系统分层

```
短期记忆：In-context messages（上下文缓冲区）
    ↓ 压缩策略管理其大小
中期记忆：GptsMemory（对话数据库，持久化）
    ↓ 对话恢复时加载
长期记忆：HybridMemory（向量存储 + Embedding 检索）
    ↓ 跨对话知识积累
磁盘快照：op_snapshots/{conv_id}/step_*.json（精确值持久化）
    ↓ 上下文压缩后按需读取

写入：write_memories() 在每轮成功后触发，同步写快照文件
恢复：build() 初始化时从数据库还原历史对话；
      Agent 可随时 read_file(snapshot_path) 还原精确操作细节
```

**四层记忆的能力对比**：

| | 短期/In-context | 向量 Memory | 磁盘快照 |
|---|---|---|---|
| **检索方式** | 直接可见 | 语义相似度 | 精确路径引用 |
| **压缩后是否保留** | 部分（Layer 1 截断，Layer 2 丢弃） | 是 | 是 |
| **精确值保证** | 是（未压缩前） | 不保证 | 是 |
| **跨对话** | 否 | 是 | 是（文件持久） |
| **适用场景** | 当前推理上下文 | 模糊回忆历史 | 精确还原操作细节 |

---

## 七、关键文件索引

| 文件路径 | 作用 |
|---|---|
| `dbgpt-core/src/dbgpt/agent/core/agent.py` | 抽象接口、AgentMessage、AgentContext（含 output_dir）定义 |
| `dbgpt-core/src/dbgpt/agent/core/base_agent.py` | ConversableAgent 完整实现，generate_reply 主循环 |
| `dbgpt-core/src/dbgpt/agent/core/role.py` | Role 基类，task_progress，`_write_op_snapshot()`，Prompt 模板 |
| `dbgpt-core/src/dbgpt/agent/core/memory/agent_memory.py` | AgentMemoryFragment（含 snapshot_path 字段） |
| `dbgpt-core/src/dbgpt/agent/core/context/manager.py` | 上下文管理编排器 |
| `dbgpt-core/src/dbgpt/agent/core/context/budget.py` | Token 预算配置与状态追踪 |
| `dbgpt-core/src/dbgpt/agent/core/context/compact.py` | 四层压缩策略，Layer 1 注入快照文件路径提示 |
| `dbgpt-core/src/dbgpt/agent/expand/react_agent.py` | ReAct 模式，read_memories() 携带快照路径提示 |
| `dbgpt-serve/src/dbgpt_serve/agent/agents/controller.py` | HTTP 入口，对话生命周期管理 |

---

## 八、设计亮点总结

| 设计点 | 说明 |
|---|---|
| **渐进式上下文管理** | 4 层压缩从轻到重，按需触发，避免不必要的 LLM 开销 |
| **任务进度持久化** | task_progress 脱离上下文缓冲区存储，压缩后不丢失已完成步骤 |
| **操作快照文件** | 每步完整 action_input + observation 卸载到磁盘，Layer 1/2 压缩后仍可精确还原，解决向量检索不可靠的问题 |
| **精确引用 vs 语义检索** | 快照文件提供精确路径引用，向量 Memory 提供语义召回，两者互补覆盖不同恢复场景 |
| **响应式兜底压缩** | Layer 4 仅在 LLM 实际报错时触发，最大化有效上下文利用 |
| **Retry 自愈机制** | Think→Review→Act→Verify 循环支持自我纠错，最多 max_retry_count 次 |
| **前端实时可见性** | context.status SSE 事件让前端实时展示 Token 使用状态和压缩层级 |
| **熔断保护** | circuit_breaker_tripped 防止压缩失败级联放大 |
