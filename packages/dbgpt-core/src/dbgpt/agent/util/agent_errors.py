"""Agent error classification for retry / failover decisions.

Inspired by hermes-agent's ``agent/error_classifier.py``: instead of relying on
a single coarse ``fail_reason`` feedback loop, errors are bucketed into
recovery-relevant categories. Each category drives a different strategy in the
agent loop: retry the same model, fail over to another model, retry the tool,
or give up.
"""

from __future__ import annotations

import enum
import logging
from typing import Optional, Union

from dbgpt.util.error_types import LLMChatError

logger = logging.getLogger(__name__)


class ErrorCategory(str, enum.Enum):
    """Recovery-relevant buckets for agent errors."""

    TOOL_EXECUTION = "tool_execution_error"
    API_TIMEOUT = "api_timeout"
    API_RATE_LIMIT = "api_rate_limit"
    API_CONTEXT_OVERFLOW = "api_context_overflow"
    INVALID_TOOL_ARGS = "invalid_tool_args"
    PERMISSION_DENIED = "permission_denied"
    RETRYABLE = "retryable"
    FATAL = "fatal"


# (category, keyword markers) — first match wins, checked case-insensitively.
_CATEGORY_MARKERS = (
    (ErrorCategory.API_TIMEOUT, ("timed out", "timeout", "time-out")),
    (ErrorCategory.API_RATE_LIMIT, ("rate limit", "rate_limited", "too many requests")),
    (
        ErrorCategory.API_CONTEXT_OVERFLOW,
        ("context length", "maximum context", "context window", "input length"),
    ),
    (
        ErrorCategory.PERMISSION_DENIED,
        ("permission", "forbidden", "unauthorized", "not allowed"),
    ),
    (
        ErrorCategory.INVALID_TOOL_ARGS,
        ("keyerror", "unexpected keyword", "missing", "invalid parameter", "argument"),
    ),
)


def _classify_text(text: str, default: ErrorCategory) -> ErrorCategory:
    lowered = text.lower()
    for category, markers in _CATEGORY_MARKERS:
        for marker in markers:
            if marker in lowered:
                return category
    return default


def classify_agent_error(
    cause: Union[BaseException, str, None],
    *,
    default: ErrorCategory = ErrorCategory.TOOL_EXECUTION,
) -> ErrorCategory:
    """Classify an agent error into a recovery-relevant category.

    Args:
        cause: An exception (its ``str`` is inspected), a message string (e.g.
            a tool failure reason), or ``None``.
        default: The category returned when no marker matches. Tool-level
            failures default to :data:`ErrorCategory.TOOL_EXECUTION`; LLM-level
            failures (detected via :class:`LLMChatError`) default to
            :data:`ErrorCategory.RETRYABLE`.
    """
    if cause is None:
        return default
    if isinstance(cause, LLMChatError):
        text = str(getattr(cause, "original_exception", None) or cause)
        return _classify_text(text, default=ErrorCategory.RETRYABLE)
    if isinstance(cause, BaseException):
        return _classify_text(str(cause), default=default)
    if isinstance(cause, str):
        return _classify_text(cause, default=default)
    return default


def is_retryable(category: ErrorCategory) -> bool:
    """Return True when the error category is worth retrying."""
    return category != ErrorCategory.FATAL


def should_failover_model(category: ErrorCategory) -> bool:
    """Return True when the error suggests trying a different model."""
    return category in (
        ErrorCategory.API_TIMEOUT,
        ErrorCategory.API_RATE_LIMIT,
        ErrorCategory.API_CONTEXT_OVERFLOW,
        ErrorCategory.RETRYABLE,
    )


def format_fail_reason(category: ErrorCategory, message: Optional[str]) -> str:
    """Build a structured feedback string for the agent loop.

    Keeps the existing ``fail_reason`` → ``observation`` feedback channel but
    tags it with the classified category so downstream logging / retry logic
    can act on it.
    """
    reason = message or "an unknown error occurred"
    return f"[{category.value}] {reason}"
