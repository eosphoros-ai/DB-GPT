"""Tests for the ContextManager orchestrator."""

import pytest

from dbgpt.agent.core.agent import AgentMessage
from dbgpt.agent.core.context.budget import ContextBudgetConfig, TokenState
from dbgpt.agent.core.context.manager import ContextManager
from dbgpt.core import ModelMessageRoleType


def _sys(content: str) -> AgentMessage:
    return AgentMessage(content=content, role=ModelMessageRoleType.SYSTEM)


def _human(content: str) -> AgentMessage:
    return AgentMessage(content=content, role=ModelMessageRoleType.HUMAN)


def _ai(content: str) -> AgentMessage:
    return AgentMessage(content=content, role=ModelMessageRoleType.AI)


def _obs(content: str) -> AgentMessage:
    return AgentMessage(
        content=f"Observation: {content}", role=ModelMessageRoleType.HUMAN
    )


def _build_long_conversation(num_rounds: int, obs_size: int = 5000):
    """Build a conversation with many rounds and large observations."""
    msgs = [_sys("You are a helpful assistant.")]
    for i in range(num_rounds):
        msgs.append(_ai(f"Thought: step {i}"))
        msgs.append(_human(f"Action: action_{i}"))
        msgs.append(_obs("x" * obs_size))
    return msgs


class TestContextManagerNormal:
    @pytest.mark.asyncio
    async def test_normal_state_passthrough(self):
        """Messages below warning threshold pass through unchanged."""
        cfg = ContextBudgetConfig(max_context_tokens=1000000, reserved_tokens=0)
        mgr = ContextManager(config=cfg)

        msgs = [_sys("system"), _ai("T"), _human("A"), _obs("short")]
        result = await mgr.manage_context(msgs, current_round=0)
        assert len(result) == len(msgs)


class TestContextManagerCompaction:
    @pytest.mark.asyncio
    async def test_layer1_and_layer2_triggered(self):
        """When token count exceeds warning, layers 1 and 2 should reduce messages."""
        # Use a very small budget so the conversation triggers compaction
        cfg = ContextBudgetConfig(
            max_context_tokens=500,
            reserved_tokens=0,
            warning_threshold=0.10,  # triggers at very low count
            min_keep_recent_rounds=1,
            min_keep_tokens=0,
            max_observation_age_rounds=2,
            truncated_observation_max_chars=50,
        )
        mgr = ContextManager(config=cfg)

        msgs = _build_long_conversation(num_rounds=5, obs_size=200)
        result = await mgr.manage_context(
            msgs, current_round=5, task_progress="step1 done"
        )
        # Should have fewer messages than original
        assert len(result) < len(msgs)

    @pytest.mark.asyncio
    async def test_circuit_breaker_skips_compaction(self):
        """When circuit breaker is tripped, compaction is skipped."""
        cfg = ContextBudgetConfig(
            max_context_tokens=100,
            reserved_tokens=0,
            warning_threshold=0.01,
            max_compact_failures=2,
        )
        mgr = ContextManager(config=cfg)

        # Trip the circuit breaker
        mgr.tracker.record_compact_failure()
        mgr.tracker.record_compact_failure()
        assert mgr.tracker.circuit_breaker_tripped

        msgs = _build_long_conversation(num_rounds=3)
        result = await mgr.manage_context(msgs, current_round=3)
        # Circuit breaker tripped → messages returned as-is
        assert len(result) == len(msgs)


class TestReactiveCompact:
    def test_reactive_compact_reduces_messages(self):
        cfg = ContextBudgetConfig()
        mgr = ContextManager(config=cfg)

        msgs = _build_long_conversation(num_rounds=10)
        result = mgr.reactive_compact(msgs)
        # Should keep system + last 2 rounds only
        assert len(result) == 1 + 2 * 3  # system + 2 rounds × 3 msgs


class TestContextManagerRecordsHistory:
    @pytest.mark.asyncio
    async def test_token_count_recorded(self):
        cfg = ContextBudgetConfig(max_context_tokens=1000000, reserved_tokens=0)
        mgr = ContextManager(config=cfg)

        msgs = [_sys("system"), _ai("T"), _human("A"), _obs("data")]
        await mgr.manage_context(msgs, current_round=0)
        assert len(mgr.tracker.token_history) == 1
        assert mgr.tracker.token_history[0] > 0
