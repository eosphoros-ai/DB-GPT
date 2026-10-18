"""Tests for agent error classification (agent_errors)."""

from dbgpt.agent.util.agent_errors import (
    ErrorCategory,
    classify_agent_error,
    format_fail_reason,
    is_retryable,
    should_failover_model,
)
from dbgpt.util.error_types import LLMChatError


class TestClassifyAgentError:
    def test_none_returns_default(self):
        assert (
            classify_agent_error(None, default=ErrorCategory.TOOL_EXECUTION)
            == ErrorCategory.TOOL_EXECUTION
        )

    def test_llm_timeout(self):
        assert (
            classify_agent_error(LLMChatError("request timed out"))
            == ErrorCategory.API_TIMEOUT
        )

    def test_llm_rate_limit(self):
        assert (
            classify_agent_error(LLMChatError("rate limit exceeded"))
            == ErrorCategory.API_RATE_LIMIT
        )

    def test_llm_context_overflow(self):
        assert (
            classify_agent_error(LLMChatError("maximum context length exceeded"))
            == ErrorCategory.API_CONTEXT_OVERFLOW
        )

    def test_llm_unknown_defaults_retryable(self):
        assert (
            classify_agent_error(LLMChatError("connection reset"))
            == ErrorCategory.RETRYABLE
        )

    def test_tool_key_error_is_invalid_args(self):
        assert (
            classify_agent_error(KeyError("missing argument 'code'"))
            == ErrorCategory.INVALID_TOOL_ARGS
        )

    def test_tool_generic_exception_defaults_tool_execution(self):
        assert (
            classify_agent_error(RuntimeError("boom")) == ErrorCategory.TOOL_EXECUTION
        )

    def test_permission_denied_string(self):
        assert (
            classify_agent_error("403 Forbidden: not allowed")
            == ErrorCategory.PERMISSION_DENIED
        )


class TestHelpers:
    def test_is_retryable(self):
        assert is_retryable(ErrorCategory.RETRYABLE)
        assert not is_retryable(ErrorCategory.FATAL)

    def test_should_failover_model(self):
        assert should_failover_model(ErrorCategory.API_TIMEOUT)
        assert should_failover_model(ErrorCategory.API_RATE_LIMIT)
        assert should_failover_model(ErrorCategory.RETRYABLE)
        assert not should_failover_model(ErrorCategory.INVALID_TOOL_ARGS)

    def test_format_fail_reason(self):
        reason = format_fail_reason(ErrorCategory.API_TIMEOUT, "timed out")
        assert reason.startswith("[api_timeout]")
        assert "timed out" in reason
