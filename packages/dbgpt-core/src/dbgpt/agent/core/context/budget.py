"""Token budget tracking for multi-layer context management."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from enum import Enum
from typing import Any, Dict, List, Optional

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
        truncated_observation_max_chars: int = 500,
        min_keep_tokens: int = 10000,
        # Tool result persistence (Layer 2/3) configuration.
        tool_result_threshold: int = 100_000,
        turn_result_budget: int = 200_000,
        preview_size: int = 1500,
        tool_overrides: Optional[Dict[str, int]] = None,
        model_context_tokens: Optional[int] = None,
        context_window_source: str = "fallback",
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
        self.configured_reserved_tokens = reserved_tokens
        self.min_keep_recent_rounds = min_keep_recent_rounds
        self.max_compact_failures = max_compact_failures
        self.max_observation_age_rounds = max_observation_age_rounds
        self.truncated_observation_max_chars = truncated_observation_max_chars
        self.min_keep_tokens = min_keep_tokens
        # Tool result persistence config (Layer 2: per-result, Layer 3: per-turn).
        self.tool_result_threshold = tool_result_threshold
        self.turn_result_budget = turn_result_budget
        self.preview_size = preview_size
        self.tool_overrides: Dict[str, int] = tool_overrides or {}
        self.model_context_tokens = model_context_tokens
        self.context_window_source = context_window_source
        self.max_output_tokens = 0

    @property
    def effective_budget(self) -> int:
        """Max tokens available after reserving space for output."""
        return self.max_context_tokens - self.reserved_tokens


async def resolve_context_budget(
    config: ContextBudgetConfig,
    llm_client: Any,
    model_name: Optional[str],
    configured_limit: Optional[int] = None,
    max_new_tokens: int = 0,
) -> ContextBudgetConfig:
    """Resolve a per-run budget without treating a fallback as a model limit.

    A deployment/adapter window limits any configured agent cap. Metadata
    retrieval is bounded and never sends a generation request to probe limits.
    """
    metadata = None
    if llm_client is not None and model_name:
        try:
            metadata = await asyncio.wait_for(
                llm_client.get_model_metadata(model_name), timeout=5
            )
        except Exception:
            logger.debug("Model window unavailable for %s", model_name, exc_info=True)
    window = getattr(metadata, "context_length", None)
    source = (getattr(metadata, "metadata", None) or {}).get(
        "context_length_source", "model_metadata"
    )
    if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
        window = None
    if source == "fallback":
        window = None
    cap = configured_limit if configured_limit and configured_limit > 0 else None
    config.model_context_tokens = window
    config.max_context_tokens = (
        min(cap, window)
        if cap and window
        else cap or window or DEFAULT_MAX_CONTEXT_TOKENS
    )
    config.context_window_source = (
        ("agent_config" if cap and (not window or cap < window) else source)
        if window or cap
        else "fallback"
    )
    output_limit = getattr(metadata, "max_output_length", None)
    if isinstance(output_limit, int) and not isinstance(output_limit, bool):
        if output_limit > 0:
            max_new_tokens = min(max_new_tokens, output_limit)
    config.max_output_tokens = max_new_tokens
    config.reserved_tokens = max(config.configured_reserved_tokens, max_new_tokens)
    if config.effective_budget <= 0:
        raise ValueError(
            f"Model {model_name}: output reservation ({config.reserved_tokens}) "
            f"must be smaller than context window ({config.max_context_tokens}). "
            "Reduce max_new_tokens/reserved_tokens or configure context_length."
        )
    # Small-window models must not retain a fixed 10k minimum indefinitely.
    config.min_keep_tokens = min(
        config.min_keep_tokens,
        int(config.effective_budget * config.warning_threshold / 2),
    )
    return config


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
        self.extra_tokens = 0

    def count_text(self, content: str) -> int:
        """Estimate tokens; proxy encodings are not provider usage measurements."""
        try:
            count = self._tokenizer.count_token(content, self.model_name)
            if count >= 0:
                return count
        except Exception:
            logger.debug("Token encoding unavailable; estimating", exc_info=True)
        # Conservative fallback also handles CJK, where 4 chars/token undercounts.
        return math.ceil(sum(1 if ord(char) > 127 else 0.25 for char in content))

    def count_messages(self, messages: list, include_extra: bool = True) -> int:
        """Count total tokens across a list of AgentMessage objects."""
        total = 3 + (self.extra_tokens if include_extra else 0)
        for msg in messages:
            content = getattr(msg, "content", None) or ""
            total += self.count_text(content) + 4
            for field in ("tool_calls", "tool_call_id", "name"):
                value = getattr(msg, field, None)
                if value:
                    total += self.count_text(json.dumps(value, ensure_ascii=False))
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
