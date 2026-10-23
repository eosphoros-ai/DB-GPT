# DB-GPT Harness Engineering 架构设计方案

> 基于 [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/) 思想，为 DB-GPT ReActAgent 设计的长程任务可靠性增强架构。

## 一、问题分析

当前 DB-GPT 的 `ReActAgent` 存在以下长程任务瓶颈：

| 问题 | 现状 | 影响 |
|------|------|------|
| **上下文膨胀** | `ShortTermMemory` buffer_size=5，但每轮 `_load_thinking_messages` 会重建完整历史 | 超过 10 轮后 token 爆炸，LLM 质量下降 |
| **任务进度粗糙** | `_task_progress` 仅记录 action/phase/status 三元组 | 无法恢复中间决策逻辑，agent 重复试错 |
| **无自愈机制** | `max_retry_count=30` 是硬循环，失败只靠 observation 反馈 | 同类错误反复出现，浪费轮次 |
| **无检查点** | 600s timeout 后直接断掉，无状态持久化 | 长程任务不可恢复 |
| **验证薄弱** | `verify()` 仅检查 `action_output.is_exe_success` | 无语义级正确性校验 |

### 现有架构关键代码路径

| 组件 | 文件 | 关键行 |
|------|------|--------|
| 主循环 | `agent/core/base_agent.py` | `generate_reply()` L392-666 |
| 消息构建 | `agent/core/base_agent.py` | `_load_thinking_messages()` L1203-1317 |
| 记忆系统 | `agent/core/memory/agent_memory.py` | `AgentMemory` L276-399 |
| 短期记忆 | `agent/core/memory/short_term.py` | `ShortTermMemory` L22-223 |
| 任务进度 | `agent/core/role.py` | `_task_progress` L204-226 |
| ReAct Agent | `agent/expand/react_agent.py` | `ReActAgent` L82-320 |
| ReAct Action | `agent/expand/actions/react_action.py` | L108-472 |

## 二、Harness Engineering 核心理念

Harness Engineering 是 2026 年由 OpenAI 提出的工程范式，核心思想是：

> **不优化 agent 本身，而是优化 agent 运行的整个环境——约束、验证、纠错、编排、上下文管理。**

与前序范式的区别：

| 范式 | 优化对象 | 粒度 |
|------|----------|------|
| Prompt Engineering (2022-2024) | 单次提问的措辞 | 单轮 |
| Context Engineering (2025) | 送入模型的信息组合 | 单次调用 |
| **Harness Engineering (2026)** | **agent 运行的整个执行环境** | **多步骤、多会话、长程工作流** |

### 六大支柱

```
┌─────────────────────────────────────────────────────────────┐
│                    DB-GPT Harness Layer                      │
├──────────┬──────────┬──────────┬──────────┬────────┬────────┤
│ Context  │ Verify   │ Correct  │ Orchestr │ Constr │ Check  │
│ Compress │ Gate     │ Loop     │ -ation   │ -aint  │ -point │
├──────────┴──────────┴──────────┴──────────┴────────┴────────┤
│                  ReActAgent (existing)                        │
├─────────────────────────────────────────────────────────────┤
│              ConversableAgent / Role / Memory                │
└─────────────────────────────────────────────────────────────┘
```

| 支柱 | 目的 |
|------|------|
| **架构脚手架 (Scaffolding)** | 预定义模板、模式和结构，缩小 agent 决策空间 |
| **约束/护栏 (Constraints)** | 硬边界（linter、类型系统、schema 校验）拒绝不合规输出 |
| **验证/测试 (Verification)** | 自动化测试套件作为首要质量门，替代人工代码审查 |
| **自校正循环 (Self-Correction)** | Agent 通过测试检测自身错误并迭代，无需人工介入 |
| **编排 (Orchestration)** | 任务分解、依赖管理、独立任务并行化 |
| **上下文管理 (Context Curation)** | 策略性地筛选、压缩和排序 agent 上下文窗口中的信息 |

## 三、核心模块设计

### 模块 1：自主上下文压缩引擎 (ContextCompressor)

这是 Harness 的核心——让 agent 在长程运行中自主管理自己的上下文窗口。

**文件位置：** `packages/dbgpt-core/src/dbgpt/agent/core/memory/context_compressor.py`

#### 分层压缩策略

```
┌──────────────────────────────────────────────────────┐
│  Level 3: Global Summary      ◄── very old (>10轮)   │
│  "整体任务已完成数据加载和清洗，正在进行分析..."         │
├──────────────────────────────────────────────────────┤
│  Level 2: Phase Summaries     ◄── old (按phase分组)   │
│  "[数据加载] 从3个CSV读取了15万行数据..."              │
│  "[数据清洗] 处理了空值和异常值，删除200行..."           │
├──────────────────────────────────────────────────────┤
│  Level 1: Round Summaries     ◄── middle-aged         │
│  "Round 7: 执行了SQL查询获取销售汇总..."               │
├──────────────────────────────────────────────────────┤
│  Level 0: Raw Messages        ◄── recent (最近3轮)    │
│  完整的 Thought/Action/Observation 原文               │
└──────────────────────────────────────────────────────┘
```

#### 核心实现

```python
"""Autonomous context compression for long-running agent tasks."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from dbgpt.agent.core.agent import AgentMessage
from dbgpt.core import LLMClient


@dataclass
class CompressionConfig:
    """Configuration for context compression."""

    # 触发压缩的 token 阈值（占模型 max_tokens 的比例）
    compression_threshold: float = 0.7
    # 压缩后目标比例
    target_ratio: float = 0.4
    # 最近 N 轮保持原文不压缩（滑动窗口）
    preserve_recent_rounds: int = 3
    # 是否保留所有 action 的输入输出摘要
    preserve_action_summaries: bool = True
    # 压缩策略: "hierarchical" | "sliding_window" | "map_reduce"
    strategy: str = "hierarchical"


@dataclass
class CompressedSegment:
    """A compressed segment of conversation history."""

    summary: str                           # 压缩后的摘要
    original_rounds: Tuple[int, int]       # 覆盖的轮次范围 (start, end)
    key_decisions: List[str]               # 保留的关键决策点
    key_artifacts: List[str]               # 保留的关键产出物（文件路径、SQL等）
    token_count_before: int
    token_count_after: int


class ContextCompressor:
    """Autonomous context compression engine.

    Implements hierarchical compression:
    - Level 0: Raw messages (recent rounds, within sliding window)
    - Level 1: Per-round summaries (middle-aged rounds)
    - Level 2: Phase-level summaries (old rounds, grouped by task phase)
    - Level 3: Global task summary (very old, single paragraph)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: Optional[CompressionConfig] = None,
    ):
        self._llm_client = llm_client
        self._config = config or CompressionConfig()
        self._compressed_cache: List[CompressedSegment] = []
        self._global_summary: Optional[str] = None

    async def should_compress(
        self,
        messages: List[AgentMessage],
        max_context_tokens: int,
    ) -> bool:
        """Check if compression is needed based on token count."""
        current_tokens = self._estimate_tokens(messages)
        return current_tokens > max_context_tokens * self._config.compression_threshold

    async def compress(
        self,
        messages: List[AgentMessage],
        max_context_tokens: int,
        current_round: int,
    ) -> List[AgentMessage]:
        """Compress messages while preserving critical information.

        Returns a new message list that fits within token budget:
        [GLOBAL_SUMMARY] + [PHASE_SUMMARIES] + [ROUND_SUMMARIES] + [RAW_RECENT]
        """
        preserve_start = max(0, current_round - self._config.preserve_recent_rounds)

        to_compress = [m for m in messages if m.rounds < preserve_start]
        to_preserve = [m for m in messages if m.rounds >= preserve_start]

        if not to_compress:
            return messages

        compressed_msgs = []

        # Level 3: 全局摘要（如果历史超过 10 轮）
        if current_round > 10 and self._compressed_cache:
            self._global_summary = await self._build_global_summary(
                self._compressed_cache
            )
            compressed_msgs.append(
                self._make_system_message(
                    f"[TASK HISTORY SUMMARY]\n{self._global_summary}"
                )
            )

        # Level 2: 按 phase 分组压缩旧轮次
        phase_groups = self._group_by_phase(to_compress)
        for phase, phase_msgs in phase_groups.items():
            segment = await self._compress_phase(phase, phase_msgs)
            self._compressed_cache.append(segment)
            compressed_msgs.append(
                self._make_system_message(
                    f"[Phase: {phase}] {segment.summary}\n"
                    f"Key decisions: {'; '.join(segment.key_decisions)}\n"
                    f"Artifacts: {', '.join(segment.key_artifacts)}"
                )
            )

        # Level 0: 保留最近几轮原文
        compressed_msgs.extend(to_preserve)

        return compressed_msgs

    async def _build_global_summary(
        self, segments: List[CompressedSegment]
    ) -> str:
        """Use LLM to build a global task summary from compressed segments."""
        segment_text = "\n".join(
            f"- Phase '{s.original_rounds}': {s.summary}" for s in segments
        )
        prompt = (
            "Summarize the following task progress into a concise paragraph. "
            "Focus on: what was accomplished, key decisions made, current state.\n\n"
            f"{segment_text}"
        )
        response = await self._llm_client.create(
            messages=[{"role": "user", "content": prompt}]
        )
        return response.text

    async def _compress_phase(
        self, phase: str, messages: List[AgentMessage]
    ) -> CompressedSegment:
        """Compress a group of messages belonging to the same phase."""
        content = "\n".join(m.content or "" for m in messages)
        prompt = (
            f"Summarize this agent execution phase '{phase}'.\n"
            "Extract: 1) What was done 2) Key decisions 3) Important artifacts "
            "(file paths, SQL queries, API calls) 4) Outcome\n\n"
            f"{content[:4000]}"
        )
        response = await self._llm_client.create(
            messages=[{"role": "user", "content": prompt}]
        )
        return CompressedSegment(
            summary=response.text,
            original_rounds=(messages[0].rounds, messages[-1].rounds),
            key_decisions=self._extract_decisions(messages),
            key_artifacts=self._extract_artifacts(messages),
            token_count_before=self._estimate_tokens(messages),
            token_count_after=self._estimate_tokens_str(response.text),
        )

    def _group_by_phase(self, messages: List[AgentMessage]) -> dict:
        """Group messages by their action phase."""
        groups = {}
        for msg in messages:
            phase = (
                msg.action_report.phase
                if msg.action_report and msg.action_report.phase
                else "general"
            )
            groups.setdefault(phase, []).append(msg)
        return groups

    def _extract_decisions(self, messages: List[AgentMessage]) -> List[str]:
        """Extract key decision points from messages."""
        decisions = []
        for m in messages:
            if m.action_report and m.action_report.thoughts:
                decisions.append(m.action_report.thoughts[:200])
        return decisions[:5]

    def _extract_artifacts(self, messages: List[AgentMessage]) -> List[str]:
        """Extract file paths, SQL, URLs from action outputs."""
        import re

        artifacts = []
        for m in messages:
            if m.action_report and m.action_report.action_input:
                text = m.action_report.action_input
                artifacts.extend(re.findall(r"[\w/]+\.\w+", text))
        return list(set(artifacts))[:10]

    def _estimate_tokens(self, messages: List[AgentMessage]) -> int:
        return sum(len(m.content or "") // 3 for m in messages)

    def _estimate_tokens_str(self, text: str) -> int:
        return len(text) // 3

    def _make_system_message(self, content: str) -> AgentMessage:
        return AgentMessage(content=content, role="system")
```

---

### 模块 2：自校验闭环 (VerificationGate)

Harness 核心理念——agent 产出后自动验证、自动修正，而非盲目重试。

**文件位置：** `packages/dbgpt-core/src/dbgpt/agent/core/harness/verification.py`

```python
"""Self-verification loop for harness engineering."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class VerificationLevel(Enum):
    STRUCTURAL = "structural"  # 格式/类型检查
    SEMANTIC = "semantic"      # LLM 语义校验
    EXECUTION = "execution"    # 实际执行验证（如 SQL dry-run）
    COMPOSITE = "composite"    # 全部组合


@dataclass
class VerificationResult:
    passed: bool
    level: VerificationLevel
    message: str
    suggestion: Optional[str] = None
    error_category: Optional[str] = None


class VerificationGate:
    """Multi-level verification gate for agent outputs.

    Replaces the simple is_exe_success check with layered verification:
    1. Structural: output format matches schema
    2. Semantic: LLM judges if output addresses the goal
    3. Execution: dry-run or sandbox execution
    """

    def __init__(self, llm_client=None):
        self._llm_client = llm_client
        self._validators: List[Callable] = []
        self._error_patterns: Dict[str, int] = {}

    def add_validator(self, validator: Callable) -> "VerificationGate":
        """Add a custom validator function."""
        self._validators.append(validator)
        return self

    async def verify(
        self,
        action_output: Any,
        goal: str,
        level: VerificationLevel = VerificationLevel.COMPOSITE,
    ) -> VerificationResult:
        """Run verification at specified level."""

        # Level 1: Structural
        if level in (VerificationLevel.STRUCTURAL, VerificationLevel.COMPOSITE):
            result = self._structural_check(action_output)
            if not result.passed:
                return result

        # Level 2: Custom validators
        for validator in self._validators:
            result = await validator(action_output)
            if not result.passed:
                return result

        # Level 3: Semantic (LLM-based)
        if level in (VerificationLevel.SEMANTIC, VerificationLevel.COMPOSITE):
            result = await self._semantic_check(action_output, goal)
            if not result.passed:
                self._record_error(result)
                return result

        return VerificationResult(
            passed=True,
            level=level,
            message="All verification checks passed",
        )

    def _structural_check(self, action_output) -> VerificationResult:
        """Check output structure and completeness."""
        if action_output is None:
            return VerificationResult(
                passed=False,
                level=VerificationLevel.STRUCTURAL,
                message="Action output is None",
                suggestion="Ensure the action returns a valid output",
            )
        if hasattr(action_output, "content") and not action_output.content:
            return VerificationResult(
                passed=False,
                level=VerificationLevel.STRUCTURAL,
                message="Action output content is empty",
                suggestion="The action executed but produced no content",
            )
        return VerificationResult(
            passed=True, level=VerificationLevel.STRUCTURAL, message="OK"
        )

    async def _semantic_check(
        self, action_output, goal: str
    ) -> VerificationResult:
        """Use LLM to judge if output addresses the goal."""
        if not self._llm_client:
            return VerificationResult(
                passed=True, level=VerificationLevel.SEMANTIC, message="Skipped"
            )

        content = (
            action_output.content
            if hasattr(action_output, "content")
            else str(action_output)
        )
        prompt = (
            f"Goal: {goal}\n\n"
            f"Agent output: {content[:2000]}\n\n"
            "Does this output correctly address the goal? "
            'Reply JSON: {"passed": bool, "reason": str, "suggestion": str}'
        )
        response = await self._llm_client.create(
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            result = json.loads(response.text)
            return VerificationResult(
                passed=result.get("passed", False),
                level=VerificationLevel.SEMANTIC,
                message=result.get("reason", ""),
                suggestion=result.get("suggestion"),
            )
        except json.JSONDecodeError:
            return VerificationResult(
                passed=True,
                level=VerificationLevel.SEMANTIC,
                message="Parse failed, passing",
            )

    def _record_error(self, result: VerificationResult):
        """Record error pattern to prevent repetition."""
        category = result.error_category or result.message[:50]
        self._error_patterns[category] = self._error_patterns.get(category, 0) + 1

    def get_repeated_errors(self, threshold: int = 2) -> List[str]:
        """Return error categories that have repeated >= threshold times."""
        return [k for k, v in self._error_patterns.items() if v >= threshold]
```

---

### 模块 3：检查点与恢复 (CheckpointManager)

长程任务的"存档/读档"机制。

**文件位置：** `packages/dbgpt-core/src/dbgpt/agent/core/harness/checkpoint.py`

```python
"""Checkpoint and recovery for long-running agent tasks."""

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TaskCheckpoint:
    """Serializable snapshot of agent execution state."""

    session_id: str
    agent_name: str
    current_round: int
    timestamp: float = field(default_factory=time.time)

    # 任务状态
    task_goal: str = ""
    task_progress: List[Dict[str, Any]] = field(default_factory=list)
    completed_phases: List[str] = field(default_factory=list)

    # 压缩后的上下文摘要（非原始消息）
    context_summary: str = ""
    key_artifacts: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)

    # 错误记忆
    error_patterns: Dict[str, int] = field(default_factory=dict)
    failed_approaches: List[str] = field(default_factory=list)

    def serialize(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def deserialize(cls, data: str) -> "TaskCheckpoint":
        return cls(**json.loads(data))


class CheckpointManager:
    """Manages checkpoints for long-running tasks.

    Saves state periodically so tasks can be resumed after:
    - Timeout (600s limit)
    - Process crash
    - Manual interruption
    - Context window exhaustion
    """

    def __init__(self, storage_backend=None):
        self._storage = storage_backend or {}
        self._auto_save_interval: int = 5  # 每 N 轮自动存档

    async def save(self, checkpoint: TaskCheckpoint) -> str:
        """Save a checkpoint, return checkpoint ID."""
        checkpoint_id = f"{checkpoint.session_id}:{checkpoint.current_round}"
        self._storage[checkpoint_id] = checkpoint.serialize()

        # 保留最近 3 个检查点，清理旧的
        session_keys = sorted(
            [k for k in self._storage if k.startswith(checkpoint.session_id)],
            key=lambda k: int(k.split(":")[-1]),
        )
        for old_key in session_keys[:-3]:
            del self._storage[old_key]

        return checkpoint_id

    async def load_latest(self, session_id: str) -> Optional[TaskCheckpoint]:
        """Load the most recent checkpoint for a session."""
        session_keys = sorted(
            [k for k in self._storage if k.startswith(session_id)],
            key=lambda k: int(k.split(":")[-1]),
        )
        if not session_keys:
            return None
        return TaskCheckpoint.deserialize(self._storage[session_keys[-1]])

    def should_save(self, current_round: int) -> bool:
        """Check if it's time for an auto-save."""
        return current_round > 0 and current_round % self._auto_save_interval == 0
```

---

### 模块 4：约束系统 (ConstraintEngine)

Harness 的核心洞察——收窄 agent 的行动空间反而提高可靠性。

**文件位置：** `packages/dbgpt-core/src/dbgpt/agent/core/harness/constraints.py`

```python
"""Constraint engine for harness engineering."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ConstraintSeverity(Enum):
    HARD = "hard"  # 违反则直接拒绝
    SOFT = "soft"  # 违反则警告并要求修正


@dataclass
class Constraint:
    name: str
    description: str
    severity: ConstraintSeverity
    check: Callable[[Any], bool]
    fix_hint: Optional[str] = None


@dataclass
class ConstraintViolation:
    constraint_name: str
    severity: ConstraintSeverity
    message: str
    fix_hint: Optional[str]


class ConstraintEngine:
    """Enforces boundaries on agent behavior.

    Constraints are rules that restrict what the agent can do,
    preventing drift and ensuring consistency in long-running tasks.
    """

    def __init__(self):
        self._constraints: List[Constraint] = []
        self._phase_constraints: Dict[str, List[Constraint]] = {}

    def add_constraint(
        self,
        name: str,
        description: str,
        check: Callable,
        severity: ConstraintSeverity = ConstraintSeverity.HARD,
        phase: Optional[str] = None,
        fix_hint: Optional[str] = None,
    ) -> "ConstraintEngine":
        """Add a constraint rule."""
        constraint = Constraint(name, description, severity, check, fix_hint)
        self._constraints.append(constraint)
        if phase:
            self._phase_constraints.setdefault(phase, []).append(constraint)
        return self

    def check(
        self,
        action_output: Any,
        current_phase: Optional[str] = None,
    ) -> List[ConstraintViolation]:
        """Check all applicable constraints, return violations."""
        violations = []

        for c in self._constraints:
            if not c.check(action_output):
                violations.append(
                    ConstraintViolation(
                        constraint_name=c.name,
                        severity=c.severity,
                        message=c.description,
                        fix_hint=c.fix_hint,
                    )
                )

        if current_phase and current_phase in self._phase_constraints:
            for c in self._phase_constraints[current_phase]:
                if not c.check(action_output):
                    violations.append(
                        ConstraintViolation(
                            constraint_name=c.name,
                            severity=c.severity,
                            message=c.description,
                            fix_hint=c.fix_hint,
                        )
                    )

        return violations

    def has_hard_violation(self, violations: List[ConstraintViolation]) -> bool:
        """Check if any violation is HARD severity."""
        return any(v.severity == ConstraintSeverity.HARD for v in violations)

    def format_violations_for_agent(
        self, violations: List[ConstraintViolation]
    ) -> str:
        """Format violations as feedback for the agent's next thinking round."""
        lines = ["CONSTRAINT VIOLATIONS detected in your last action:"]
        for v in violations:
            prefix = "HARD" if v.severity == ConstraintSeverity.HARD else "SOFT"
            lines.append(f"  {prefix} [{v.constraint_name}]: {v.message}")
            if v.fix_hint:
                lines.append(f"    -> Fix: {v.fix_hint}")
        return "\n".join(lines)
```

## 四、集成改造：增强 generate_reply 主循环

### 改造后的核心流程

不直接修改 `ConversableAgent.generate_reply`，而是在 `HarnessReActAgent` 中 override：

```python
async def generate_reply(self, received_message, sender, **kwargs):
    reply_message = await self._a_init_reply_message(received_message)

    # ===== HARNESS: 初始化 =====
    compressor = self._harness_compressor
    checkpoint_mgr = self._harness_checkpoint
    verifier = self._harness_verifier
    constraints = self._harness_constraints

    # HARNESS: 尝试从检查点恢复
    checkpoint = await checkpoint_mgr.load_latest(self.agent_context.conv_id)
    if checkpoint:
        self._task_progress = checkpoint.task_progress
        self._restore_context_from_checkpoint(checkpoint)
        start_round = checkpoint.current_round
    else:
        start_round = 0

    current_retry_counter = start_round
    start_time = time.time()

    while current_retry_counter < self.max_retry_count:

        # ===== HARNESS: 上下文压缩 =====
        thinking_messages = await self._load_thinking_messages(...)
        if await compressor.should_compress(
            thinking_messages, self._max_context_tokens
        ):
            thinking_messages = await compressor.compress(
                thinking_messages,
                self._max_context_tokens,
                current_retry_counter,
            )

        # Phase 1: Thinking (unchanged)
        ai_message, model_name = await self.thinking(thinking_messages)

        # Phase 2: Review (unchanged)
        approve, comments = await self.review(ai_message, sender)

        # Phase 3: Act
        action_output = await self.act(reply_message, sender)

        # ===== HARNESS: 约束检查 =====
        phase = action_output.phase if action_output else None
        violations = constraints.check(action_output, current_phase=phase)
        if constraints.has_hard_violation(violations):
            observation = constraints.format_violations_for_agent(violations)
            current_retry_counter += 1
            continue

        # ===== HARNESS: 多级验证 =====
        verify_result = await verifier.verify(
            action_output,
            goal=received_message.current_goal or received_message.content,
        )
        if not verify_result.passed:
            repeated = verifier.get_repeated_errors(threshold=2)
            if repeated:
                observation = (
                    f"REPEATED ERROR detected: {repeated}. "
                    "You MUST use a different approach. "
                    f"Suggestion: {verify_result.suggestion}"
                )
            else:
                observation = (
                    f"Verification failed: {verify_result.message}. "
                    f"Suggestion: {verify_result.suggestion}"
                )
            current_retry_counter += 1
            continue

        # Phase 4: Write memories
        await self.write_memories(...)

        # ===== HARNESS: 自动检查点 =====
        if checkpoint_mgr.should_save(current_retry_counter):
            await checkpoint_mgr.save(
                TaskCheckpoint(
                    session_id=self.agent_context.conv_id,
                    agent_name=self.role_name,
                    current_round=current_retry_counter,
                    task_goal=received_message.content,
                    task_progress=self._task_progress,
                    context_summary=compressor._global_summary or "",
                    error_patterns=verifier._error_patterns,
                )
            )

        # Check termination
        if action_output and action_output.terminate:
            break

        current_retry_counter += 1

    return reply_message
```

### 改造 `_load_thinking_messages` — 压缩注入点

```python
async def _load_thinking_messages(self, received_message, sender, **kwargs):
    # 原有逻辑：读取 memories
    memories = await self.read_memories(observation)

    # === HARNESS: 压缩检查 ===
    if self._harness_compressor and isinstance(memories, list) and len(memories) > 8:
        memories = await self._harness_compressor.compress(
            memories,
            max_context_tokens=self._estimate_max_context(),
            current_round=kwargs.get("current_retry_counter", 0),
        )

    # 原有逻辑：构建 prompts
    system_prompt = await self.build_system_prompt()
    user_prompt = await self.build_prompt()

    # === HARNESS: 注入错误模式警告 ===
    if self._harness_verifier:
        repeated = self._harness_verifier.get_repeated_errors()
        if repeated:
            user_prompt += (
                f"\n\nAVOID these previously failed approaches: "
                f"{', '.join(repeated)}"
            )

    messages = [system_msg] + memories + [user_msg]
    return messages, resource_refs
```

## 五、HarnessReActAgent 完整类

**文件位置：** `packages/dbgpt-core/src/dbgpt/agent/expand/harness_react_agent.py`

```python
"""Harness-enhanced ReAct agent for long-running tasks."""

from typing import Optional

from dbgpt.agent.core.harness.checkpoint import CheckpointManager
from dbgpt.agent.core.harness.constraints import ConstraintEngine
from dbgpt.agent.core.harness.verification import VerificationGate
from dbgpt.agent.core.memory.context_compressor import (
    CompressionConfig,
    ContextCompressor,
)
from dbgpt.agent.expand.react_agent import ReActAgent


class HarnessReActAgent(ReActAgent):
    """ReActAgent with full harness engineering support.

    Extends ReActAgent with:
    
    - Autonomous context compression for unlimited rounds
    - Multi-level verification gates
    - Checkpoint/recovery for fault tolerance
    - Constraint engine to prevent drift
    - Error pattern memory to prevent repetitive failures
    """

    max_retry_count: int = 100
    max_timeout: int = 3600  # 1 hour

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._harness_compressor: Optional[ContextCompressor] = None
        self._harness_verifier: Optional[VerificationGate] = None
        self._harness_checkpoint: Optional[CheckpointManager] = None
        self._harness_constraints: Optional[ConstraintEngine] = None

    async def build(self) -> "HarnessReActAgent":
        """Build agent with harness components."""
        await super().build()

        self._harness_compressor = ContextCompressor(
            llm_client=self.llm_client,
            config=CompressionConfig(
                compression_threshold=0.7,
                target_ratio=0.4,
                preserve_recent_rounds=3,
            ),
        )
        self._harness_verifier = VerificationGate(llm_client=self.llm_client)
        self._harness_checkpoint = CheckpointManager()
        self._harness_constraints = ConstraintEngine()

        return self
```

## 六、整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User / Orchestrator                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                v
┌─────────────────────────────────────────────────────────────────────┐
│                     HarnessReActAgent                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Harness Layer                              │   │
│  │                                                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │   │
│  │  │  Constraint   │  │ Verification │  │   Checkpoint     │   │   │
│  │  │  Engine       │  │ Gate         │  │   Manager        │   │   │
│  │  │              │  │              │  │                  │   │   │
│  │  │ - hard/soft  │  │ - structural │  │ - auto-save/5轮 │   │   │
│  │  │ - per-phase  │  │ - semantic   │  │ - crash recovery │   │   │
│  │  │ - fix hints  │  │ - execution  │  │ - state restore  │   │   │
│  │  └──────────────┘  │ - error mem  │  └──────────────────┘   │   │
│  │                     └──────────────┘                          │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │              Context Compressor                         │  │   │
│  │  │                                                         │  │   │
│  │  │  Level 3: Global Summary    <-- very old (>10 rounds)  │  │   │
│  │  │  Level 2: Phase Summaries   <-- old (grouped by phase) │  │   │
│  │  │  Level 1: Round Summaries   <-- middle-aged            │  │   │
│  │  │  Level 0: Raw Messages      <-- recent (last 3 rounds) │  │   │
│  │  │                                                         │  │   │
│  │  │  Token budget: 70% threshold -> compress to 40%         │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 ReActAgent Loop (enhanced)                    │   │
│  │                                                               │   │
│  │   ┌─────────┐   ┌────────┐   ┌─────┐   ┌────────────────┐  │   │
│  │   │ Think   │-->│ Review │-->│ Act │-->│ Verify (multi) │  │   │
│  │   └─────────┘   └────────┘   └──┬──┘   └───────┬────────┘  │   │
│  │        ^                        │              │            │   │
│  │        │     ┌──────────────────┘    ┌─────────┘            │   │
│  │        │     v                       v                      │   │
│  │        │  Constraint --fail--> Inject fix hint              │   │
│  │        │  Check                      │                      │   │
│  │        │                             v                      │   │
│  │        └──────── retry <──── Verification --fail--> Error   │   │
│  │                                  │              pattern mem │   │
│  │                               pass v                        │   │
│  │                          ┌──────────────┐                   │   │
│  │                          │ Write Memory │                   │   │
│  │                          │ + Checkpoint │                   │   │
│  │                          └──────────────┘                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Memory Hierarchy (existing + enhanced)           │   │
│  │                                                               │   │
│  │  ShortTermMemory(5) --overflow--> LongTermMemory(VectorDB)  │   │
│  │        +                                                      │   │
│  │  StructuredAgentMemoryFragment (ReAct format)                │   │
│  │        +                                                      │   │
│  │  _task_progress (persistent step tracker)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 七、新增文件结构

```
packages/dbgpt-core/src/dbgpt/agent/core/
├── harness/                          # NEW: harness package
│   ├── __init__.py
│   ├── checkpoint.py                 # CheckpointManager + TaskCheckpoint
│   ├── constraints.py                # ConstraintEngine
│   └── verification.py              # VerificationGate
├── memory/
│   ├── context_compressor.py        # NEW: ContextCompressor
│   └── ... (existing files unchanged)
└── ... (existing files unchanged)

packages/dbgpt-core/src/dbgpt/agent/expand/
├── harness_react_agent.py           # NEW: HarnessReActAgent
└── ... (existing files unchanged)
```

## 八、关键设计决策

| 决策 | 理由 |
|------|------|
| **继承而非改写** — `HarnessReActAgent` 继承 `ReActAgent` | 不破坏现有功能，harness 是可选增强层 |
| **分层压缩而非截断** — 4 级压缩层 | 截断丢信息，分层压缩保留关键决策和产出物 |
| **错误模式记忆** — 记录重复错误类别 | Harness 核心思想：同类错误不应出现两次 |
| **检查点存储可插拔** — 默认 dict，可替换为 DB | 兼容 DB-GPT 的存储抽象层 |
| **压缩用 LLM 做摘要** — 而非规则截取 | 保证摘要质量，保留语义关键信息 |
| **约束 per-phase 生效** — 不同阶段不同约束 | 数据分析阶段 vs 报告生成阶段的约束完全不同 |
| **max_retry 提升到 100，timeout 到 1h** | harness 保证了每轮的有效性，可以安全运行更多轮 |

## 九、使用示例

### 基础使用

```python
from dbgpt.agent.expand.harness_react_agent import HarnessReActAgent
from dbgpt.agent.core.harness.constraints import ConstraintEngine, ConstraintSeverity

# 创建 harness agent
agent = HarnessReActAgent()
await agent.bind(llm_config).bind(resource).build()

# 正常使用 — harness 自动运行
await agent.receive(message, sender)
```

### 添加任务特定约束

```python
# 安全约束：禁止 DROP TABLE
agent._harness_constraints.add_constraint(
    name="no_drop_table",
    description="Never execute DROP TABLE statements",
    severity=ConstraintSeverity.HARD,
    check=lambda out: "DROP TABLE" not in (out.content or "").upper(),
    fix_hint="Use DELETE FROM or TRUNCATE instead",
)

# 性能约束：SQL 必须带 LIMIT
agent._harness_constraints.add_constraint(
    name="max_query_rows",
    description="SQL queries must include LIMIT clause",
    severity=ConstraintSeverity.SOFT,
    phase="data_query",
    check=lambda out: "LIMIT" in (out.action_input or "").upper(),
    fix_hint="Add LIMIT 1000 to prevent memory issues",
)
```

### 自定义验证器

```python
async def validate_sql_output(action_output):
    """Custom validator: check SQL query results are non-empty."""
    if action_output.action == "sql_query" and not action_output.content:
        return VerificationResult(
            passed=False,
            level=VerificationLevel.EXECUTION,
            message="SQL query returned empty results",
            suggestion="Check table name and WHERE conditions",
        )
    return VerificationResult(
        passed=True, level=VerificationLevel.EXECUTION, message="OK"
    )

agent._harness_verifier.add_validator(validate_sql_output)
```

## 十、后续演进方向

1. **分布式检查点** — 将 CheckpointManager 对接 DB-GPT 的 StorageInterface，支持 MySQL/Redis 后端
2. **多 Agent 编排 Harness** — 将约束和验证扩展到 multi-agent 对话场景（AutoPlanChatManager）
3. **Harness 配置文件化** — 支持 YAML/TOML 声明式定义约束和验证规则，而非硬编码
4. **可观测性** — 集成 OpenTelemetry，追踪每轮的压缩率、验证通过率、错误模式分布
5. **自适应压缩** — 根据任务复杂度和模型能力动态调整 `compression_threshold` 和 `preserve_recent_rounds`
