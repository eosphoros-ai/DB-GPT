"""Tests for the ContextManager orchestrator."""

import random
import string

import pytest

from dbgpt.agent.core.agent import AgentMessage
from dbgpt.agent.core.context.budget import ContextBudgetConfig
from dbgpt.agent.core.context.manager import ContextManager
from dbgpt.core import ModelMessageRoleType

_RANDOM_ALPHABET = string.ascii_letters + string.digits


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


def _build_detailed_conversation(num_rounds: int, obs_size: int = 200):
    """Build a conversation whose size is stable across tokenizer backends.

    The observation bodies are incompressible per-character text so that a
    character-counting tokenizer and tiktoken agree closely on the total size.
    """

    def _random_text(size: int, seed: int) -> str:
        rnd = random.Random(seed)
        return "".join(rnd.choice(_RANDOM_ALPHABET) for _ in range(size))

    msgs = [_sys("You are a helpful assistant.")]
    for i in range(num_rounds):
        msgs.append(_ai(f"Thought: step {i}"))
        msgs.append(_human("Action: " + _random_text(40, i)))
        msgs.append(_obs(_random_text(obs_size, i)))
    return msgs


class _CharTokenizer:
    """Deterministic stand-in for the tokenizer (no optional backend needed)."""

    def count_token(self, messages, model_name=None):
        return len(messages)


class _RecordingLLMClient:
    """Minimal AIWrapper stand-in: layer 3 only calls ``generate_text``."""

    def __init__(self):
        self.calls = []

    async def generate_text(self, prompt, llm_model=None, **kwargs):
        self.calls.append((llm_model, prompt))
        return "SUMMARY-OF-EARLIER-ROUNDS"


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
    @pytest.mark.asyncio
    async def test_reactive_compact_reduces_messages(self):
        cfg = ContextBudgetConfig()
        mgr = ContextManager(config=cfg)

        msgs = _build_long_conversation(num_rounds=10)
        result = await mgr.reactive_compact(msgs)
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

    @pytest.mark.asyncio
    async def test_skip_status_emit_when_effective_budget_invalid(self):
        received = []

        async def _on_status(status):
            received.append(status)

        cfg = ContextBudgetConfig(max_context_tokens=1, reserved_tokens=10)
        mgr = ContextManager(config=cfg, on_status_event=_on_status)

        msgs = [_sys("system"), _ai("T"), _human("A"), _obs("data")]
        await mgr.manage_context(msgs, current_round=0)
        assert received == []


def _layer3_config() -> ContextBudgetConfig:
    """A budget where layers 1+2 cannot get back under the error threshold."""
    return ContextBudgetConfig(
        max_context_tokens=5000,
        reserved_tokens=0,
        min_keep_recent_rounds=6,
        min_keep_tokens=4800,
        max_observation_age_rounds=100,
        truncated_observation_max_chars=10,
    )


class TestLayer3FullContextCompression:
    @pytest.mark.asyncio
    async def test_layer3_summarizes_with_the_configured_model(self):
        """Layer 3 must reach the LLM with the model name from the constructor."""
        llm_client = _RecordingLLMClient()
        mgr = ContextManager(
            config=_layer3_config(), model_name="gpt-4o-mini", llm_client=llm_client
        )
        mgr.tracker._tokenizer = _CharTokenizer()

        msgs = _build_detailed_conversation(num_rounds=35)
        result = await mgr.manage_context(msgs, current_round=35, task_progress="done")

        assert len(llm_client.calls) == 1
        llm_model, prompt = llm_client.calls[0]
        assert llm_model == "gpt-4o-mini"
        assert "## Conversation to summarize" in prompt
        # Layer 3 summarized the rounds layer 2 could not drop.
        assert "Thought: step" in prompt

        contents = [m.content or "" for m in result]
        assert any("SUMMARY-OF-EARLIER-ROUNDS" in content for content in contents)
        # system prompt, then the generated summary, then the recent rounds
        summary_index = next(
            i
            for i, content in enumerate(contents)
            if "SUMMARY-OF-EARLIER-ROUNDS" in content
        )
        assert summary_index == 1
        assert len(result) < len(msgs)

    @pytest.mark.asyncio
    async def test_layer3_without_model_name_skips_summarization(self):
        """Without a model name layer 3 is skipped instead of blowing up."""
        llm_client = _RecordingLLMClient()
        mgr = ContextManager(config=_layer3_config(), llm_client=llm_client)
        mgr.tracker._tokenizer = _CharTokenizer()

        msgs = _build_detailed_conversation(num_rounds=35)
        result = await mgr.manage_context(msgs, current_round=35)

        assert llm_client.calls == []
        contents = [m.content or "" for m in result]
        assert not any("SUMMARY-OF-EARLIER-ROUNDS" in content for content in contents)

    @pytest.mark.asyncio
    async def test_layer3_without_model_name_does_not_record_a_failure(self):
        """Skipping layer 3 must not count against the compaction circuit breaker.

        `FullContextCompression.compact` deliberately returns early when it has
        no model name, so nothing failed. Reading an attribute that does not
        exist made that branch raise instead, and the surrounding
        `except Exception` recorded it as a compaction failure; after
        `max_compact_failures` calls the breaker trips and compaction is
        disabled for the rest of the session.
        """
        llm_client = _RecordingLLMClient()
        mgr = ContextManager(config=_layer3_config(), llm_client=llm_client)
        mgr.tracker._tokenizer = _CharTokenizer()

        # One more call than the breaker tolerates failures.
        for _ in range(mgr.tracker.config.max_compact_failures + 1):
            msgs = _build_detailed_conversation(num_rounds=35)
            await mgr.manage_context(msgs, current_round=35)

            assert not mgr.tracker.circuit_breaker_tripped, (
                "layer 3 skipped for want of a model name, so no compaction "
                "failure should have been recorded"
            )
