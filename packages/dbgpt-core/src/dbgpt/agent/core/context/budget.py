"""Token budget tracking for multi-layer context management."""

from __future__ import annotations

import logging
from enum import Enum
from typing import List, Optional

from dbgpt.model.utils.token_utils import ProxyTokenizerWrapper

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXT_TOKENS = 120000


class TokenState(Enum):
    """Context budget state levels."""

    NORMAL = "normal"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    OVERFLOW = "overflow"

    def __ge__(self, other: "TokenState") -> bool:
        order = list(TokenState)
        return order.index(self) >= order.index(other)

    def __gt__(self, other: "TokenState") -> bool:
        order = list(TokenState)
        return order.index(self) > order.index(other)

    def __le__(self, other: "TokenState") -> bool:
        order = list(TokenState)
        return order.index(self) <= order.index(other)

    def __lt__(self, other: "TokenState") -> bool:
        order = list(TokenState)
        return order.index(self) < order.index(other)


class ContextBudgetConfig:
    """Configuration for context budget management."""

    def __init__(
        self,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        warning_threshold: float = 0.70,
        error_threshold: float = 0.90,
        critical_threshold: float = 0.95,
        reserved_tokens: int = 4096,
        min_keep_recent_rounds: int = 3,
        max_compact_failures: int = 3,
        max_observation_age_rounds: int = 5,
        truncated_observation_max_chars: int = 200,
        min_keep_tokens: int = 10000,
    ):
        # `max_context_tokens <= 0` means "auto-detect from model metadata".
        # If the caller could not resolve metadata, keep the context window usable
        # by falling back to the system default budget instead of leaving it at 0.
        self.max_context_tokens = (
            max_context_tokens
            if max_context_tokens and max_context_tokens > 0
            else DEFAULT_MAX_CONTEXT_TOKENS
        )
        self.warning_threshold = warning_threshold
        self.error_threshold = error_threshold
        self.critical_threshold = critical_threshold
        self.reserved_tokens = reserved_tokens
        self.min_keep_recent_rounds = min_keep_recent_rounds
        self.max_compact_failures = max_compact_failures
        self.max_observation_age_rounds = max_observation_age_rounds
        self.truncated_observation_max_chars = truncated_observation_max_chars
        self.min_keep_tokens = min_keep_tokens

    @property
    def effective_budget(self) -> int:
        """Max tokens available after reserving space for output."""
        return self.max_context_tokens - self.reserved_tokens


class ContextBudgetTracker:
    """Tracks token usage and determines context budget state."""

    def __init__(
        self,
        config: ContextBudgetConfig,
        model_name: Optional[str] = None,
    ):
        self.config = config
        self.model_name = model_name
        self._tokenizer = ProxyTokenizerWrapper()
        self._token_history: List[int] = []
        self._compact_failure_count: int = 0

    def count_messages(self, messages: list) -> int:
        """Count total tokens across a list of AgentMessage objects."""
        total = 0
        for msg in messages:
            content = getattr(msg, "content", None) or ""
            count = self._tokenizer.count_token(content, self.model_name)
            if count < 0:
                # Fallback: rough estimate of 4 chars per token
                count = len(content) // 4
            total += count
        return total

    def get_state(self, token_count: int) -> TokenState:
        """Determine budget state based on current token count."""
        budget = self.config.effective_budget
        if budget <= 0:
            return TokenState.OVERFLOW

        ratio = token_count / budget
        if ratio >= 1.0:
            return TokenState.OVERFLOW
        elif ratio >= self.config.critical_threshold:
            return TokenState.CRITICAL
        elif ratio >= self.config.error_threshold:
            return TokenState.ERROR
        elif ratio >= self.config.warning_threshold:
            return TokenState.WARNING
        else:
            return TokenState.NORMAL

    def record_token_count(self, count: int) -> None:
        """Record a token count for history tracking."""
        self._token_history.append(count)

    def record_compact_success(self) -> None:
        """Reset failure counter on successful compaction."""
        self._compact_failure_count = 0

    def record_compact_failure(self) -> None:
        """Increment failure counter."""
        self._compact_failure_count += 1
        logger.warning(
            "Context compaction failed (consecutive failures: %d/%d)",
            self._compact_failure_count,
            self.config.max_compact_failures,
        )

    @property
    def circuit_breaker_tripped(self) -> bool:
        """True if too many consecutive compaction failures occurred."""
        return self._compact_failure_count >= self.config.max_compact_failures

    @property
    def token_history(self) -> List[int]:
        """Return recorded token count history."""
        return list(self._token_history)
