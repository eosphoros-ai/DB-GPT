"""Tests for context budget tracking."""

from dbgpt.agent.core.context.budget import (
    DEFAULT_MAX_CONTEXT_TOKENS,
    ContextBudgetConfig,
    ContextBudgetTracker,
    TokenState,
)


class TestTokenState:
    def test_ordering(self):
        assert TokenState.NORMAL < TokenState.WARNING
        assert TokenState.WARNING < TokenState.ERROR
        assert TokenState.ERROR < TokenState.CRITICAL
        assert TokenState.CRITICAL < TokenState.OVERFLOW

    def test_ge(self):
        assert TokenState.ERROR >= TokenState.WARNING
        assert TokenState.WARNING >= TokenState.WARNING
        assert not (TokenState.NORMAL >= TokenState.WARNING)


class TestContextBudgetConfig:
    def test_defaults(self):
        cfg = ContextBudgetConfig()
        assert cfg.max_context_tokens == 120000
        assert cfg.warning_threshold == 0.70
        assert cfg.error_threshold == 0.90
        assert cfg.reserved_tokens == 4096

    def test_effective_budget(self):
        cfg = ContextBudgetConfig(max_context_tokens=100000, reserved_tokens=5000)
        assert cfg.effective_budget == 95000

    def test_custom_thresholds(self):
        cfg = ContextBudgetConfig(
            warning_threshold=0.60,
            error_threshold=0.80,
            critical_threshold=0.90,
        )
        assert cfg.warning_threshold == 0.60
        assert cfg.error_threshold == 0.80
        assert cfg.critical_threshold == 0.90

    def test_non_positive_max_context_tokens_falls_back_to_default(self):
        cfg = ContextBudgetConfig(max_context_tokens=0)
        assert cfg.max_context_tokens == DEFAULT_MAX_CONTEXT_TOKENS

        cfg = ContextBudgetConfig(max_context_tokens=-1)
        assert cfg.max_context_tokens == DEFAULT_MAX_CONTEXT_TOKENS


class _FakeMsg:
    """Lightweight message stub for testing."""

    def __init__(self, content: str):
        self.content = content


class TestContextBudgetTracker:
    def _make_tracker(self, max_tokens=1000, reserved=100):
        cfg = ContextBudgetConfig(
            max_context_tokens=max_tokens, reserved_tokens=reserved
        )
        return ContextBudgetTracker(cfg)

    def test_count_messages(self):
        tracker = self._make_tracker()
        msgs = [_FakeMsg("hello world"), _FakeMsg("test")]
        count = tracker.count_messages(msgs)
        assert count > 0

    def test_get_state_normal(self):
        tracker = self._make_tracker(max_tokens=10000, reserved=0)
        # 10% of budget → NORMAL
        assert tracker.get_state(1000) == TokenState.NORMAL

    def test_get_state_warning(self):
        tracker = self._make_tracker(max_tokens=10000, reserved=0)
        # 75% → WARNING
        assert tracker.get_state(7500) == TokenState.WARNING

    def test_get_state_error(self):
        tracker = self._make_tracker(max_tokens=10000, reserved=0)
        # 92% → ERROR
        assert tracker.get_state(9200) == TokenState.ERROR

    def test_get_state_critical(self):
        tracker = self._make_tracker(max_tokens=10000, reserved=0)
        # 96% → CRITICAL
        assert tracker.get_state(9600) == TokenState.CRITICAL

    def test_get_state_overflow(self):
        tracker = self._make_tracker(max_tokens=10000, reserved=0)
        # 100%+ → OVERFLOW
        assert tracker.get_state(10000) == TokenState.OVERFLOW

    def test_circuit_breaker_not_tripped_initially(self):
        tracker = self._make_tracker()
        assert not tracker.circuit_breaker_tripped

    def test_circuit_breaker_trips_after_max_failures(self):
        tracker = self._make_tracker()
        for _ in range(3):
            tracker.record_compact_failure()
        assert tracker.circuit_breaker_tripped

    def test_circuit_breaker_resets_on_success(self):
        tracker = self._make_tracker()
        tracker.record_compact_failure()
        tracker.record_compact_failure()
        tracker.record_compact_success()
        assert not tracker.circuit_breaker_tripped

    def test_token_history(self):
        tracker = self._make_tracker()
        tracker.record_token_count(100)
        tracker.record_token_count(200)
        assert tracker.token_history == [100, 200]
