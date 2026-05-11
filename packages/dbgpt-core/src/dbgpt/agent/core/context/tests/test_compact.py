"""Tests for four-layer compaction strategies."""

from dbgpt.agent.core.agent import AgentMessage
from dbgpt.agent.core.context.budget import ContextBudgetConfig, ContextBudgetTracker
from dbgpt.agent.core.context.compact import (
    ObservationMicroCompact,
    ReactiveCompact,
    SessionMemoryCompact,
    _detect_round_boundaries,
    _is_observation_message,
    _is_system_message,
)
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


def _make_tracker(**kwargs) -> ContextBudgetTracker:
    cfg = ContextBudgetConfig(**kwargs)
    return ContextBudgetTracker(cfg)


class TestHelpers:
    def test_is_system_message(self):
        assert _is_system_message(_sys("x"))
        assert not _is_system_message(_human("x"))

    def test_is_observation_message(self):
        assert _is_observation_message(_obs("data"))
        assert not _is_observation_message(_human("Question: what"))
        assert not _is_observation_message(_ai("Thought: think"))

    def test_detect_round_boundaries(self):
        msgs = [
            _sys("system prompt"),
            _ai("Thought: step 1"),
            _human("Action: do something"),
            _obs("result 1"),
            _ai("Thought: step 2"),
            _human("Action: do more"),
            _obs("result 2"),
        ]
        rounds = _detect_round_boundaries(msgs)
        # System message is excluded, so 2 rounds
        assert len(rounds) == 2
        # Each round ends with an observation
        assert len(rounds[0]) == 3  # ai, human, obs
        assert len(rounds[1]) == 3

    def test_detect_round_incomplete_round(self):
        msgs = [_ai("Thought: thinking"), _human("Action: act")]
        rounds = _detect_round_boundaries(msgs)
        # One incomplete round
        assert len(rounds) == 1


class TestObservationMicroCompact:
    def test_truncates_old_observations(self):
        tracker = _make_tracker(
            max_observation_age_rounds=2, truncated_observation_max_chars=50
        )
        layer1 = ObservationMicroCompact()

        long_content = "x" * 5000
        msgs = [
            _sys("system"),
            # Round 0
            _ai("Thought: 1"),
            _human("Action: a"),
            _obs(long_content),
            # Round 1
            _ai("Thought: 2"),
            _human("Action: b"),
            _obs(long_content),
            # Round 2 (recent, should not be truncated)
            _ai("Thought: 3"),
            _human("Action: c"),
            _obs(long_content),
        ]
        result = layer1.compact(msgs, current_round=5, tracker=tracker)
        # First observation (round 0) should be truncated
        obs0 = result[3]
        assert len(obs0.content) < 300
        assert "[truncated]" in obs0.content

    def test_preserves_recent_observations(self):
        tracker = _make_tracker(
            max_observation_age_rounds=5, truncated_observation_max_chars=50
        )
        layer1 = ObservationMicroCompact()

        msgs = [
            _ai("Thought: 1"),
            _human("Action: a"),
            _obs("short result"),
        ]
        result = layer1.compact(msgs, current_round=2, tracker=tracker)
        obs = result[2]
        assert obs.content == "Observation: short result"


class TestSessionMemoryCompact:
    def test_drops_old_rounds(self):
        tracker = _make_tracker(min_keep_recent_rounds=1, min_keep_tokens=0)
        layer2 = SessionMemoryCompact()

        msgs = [
            _sys("system"),
            # Round 0
            _ai("Thought: old"),
            _human("Action: old"),
            _obs("old result"),
            # Round 1
            _ai("Thought: old2"),
            _human("Action: old2"),
            _obs("old result2"),
            # Round 2 (recent)
            _ai("Thought: recent"),
            _human("Action: recent"),
            _obs("recent result"),
        ]
        result = layer2.compact(msgs, task_progress="step1,step2", tracker=tracker)
        # Should keep system + last round
        assert result[0].content == "system"
        # Should have dropped old rounds
        assert len(result) < len(msgs)
        # Last round should be intact
        assert any("recent" in (m.content or "") for m in result)

    def test_preserves_minimum_rounds(self):
        tracker = _make_tracker(min_keep_recent_rounds=5)
        layer2 = SessionMemoryCompact()

        msgs = [
            _sys("system"),
            _ai("Thought: 1"),
            _human("Action: a"),
            _obs("result"),
        ]
        result = layer2.compact(msgs, task_progress=None, tracker=tracker)
        # Only 1 round, min_keep=5 → no change
        assert len(result) == len(msgs)

    def test_triplet_integrity(self):
        """Ensure complete triplets are never split."""
        tracker = _make_tracker(min_keep_recent_rounds=1, min_keep_tokens=0)
        layer2 = SessionMemoryCompact()

        msgs = [
            _sys("system"),
            _ai("T1"),
            _human("A1"),
            _obs("O1"),
            _ai("T2"),
            _human("A2"),
            _obs("O2"),
        ]
        result = layer2.compact(msgs, task_progress="done", tracker=tracker)
        # Non-system messages should form complete triplets
        non_sys = [m for m in result if m.role != ModelMessageRoleType.SYSTEM]
        assert len(non_sys) % 3 == 0


class TestReactiveCompact:
    def test_emergency_keeps_last_2_rounds(self):
        tracker = _make_tracker()
        layer4 = ReactiveCompact()

        msgs = [
            _sys("system"),
            _ai("T1"),
            _human("A1"),
            _obs("O1"),
            _ai("T2"),
            _human("A2"),
            _obs("O2"),
            _ai("T3"),
            _human("A3"),
            _obs("O3"),
        ]
        result = layer4.compact(msgs, tracker=tracker)
        assert result[0].content == "system"
        # 1 system + 2 rounds × 3 msgs = 7
        assert len(result) == 7

    def test_noop_if_few_rounds(self):
        tracker = _make_tracker()
        layer4 = ReactiveCompact()

        msgs = [_sys("sys"), _ai("T"), _human("A"), _obs("O")]
        result = layer4.compact(msgs, tracker=tracker)
        assert len(result) == len(msgs)
