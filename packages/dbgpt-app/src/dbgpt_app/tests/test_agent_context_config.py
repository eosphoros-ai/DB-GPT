"""Tests for agent context configuration."""

import pytest

from dbgpt.util.configure.manager import ConfigurationManager
from dbgpt_app.config import AgentContextParameters
from dbgpt_app.scene.base_chat import DEFAULT_MAX_NEW_TOKENS, resolve_max_new_tokens


def test_resolve_max_new_tokens_request_takes_precedence():
    """The per-request value wins over the application config."""
    assert resolve_max_new_tokens(2048, 1024) == 2048


def test_resolve_max_new_tokens_config_used_when_request_omitted():
    """Fall back to the configured value when the request omits the field."""
    assert resolve_max_new_tokens(None, 2048) == 2048


def test_resolve_max_new_tokens_default_when_both_omitted():
    """Fall back to the shared 4096 default so clients are not regressed."""
    assert resolve_max_new_tokens(None, None) == DEFAULT_MAX_NEW_TOKENS
    assert DEFAULT_MAX_NEW_TOKENS == 4096


@pytest.mark.parametrize("requested", [0, -1])
def test_resolve_max_new_tokens_non_positive_request_falls_through(
    requested,
):
    """Treat non-positive request values as unset, matching the agent resolver."""
    assert resolve_max_new_tokens(requested, 2048) == 2048
    assert resolve_max_new_tokens(requested, None) == DEFAULT_MAX_NEW_TOKENS


def test_resolve_max_new_tokens_accepts_numeric_strings():
    """Keep the previous behavior of coercing numeric strings to ints."""
    assert resolve_max_new_tokens("2048", 1024) == 2048
    assert resolve_max_new_tokens(None, "2048") == 2048


def test_max_new_tokens_accepts_config_value():
    config = AgentContextParameters(max_new_tokens=16384)

    assert config.max_new_tokens == 16384


@pytest.mark.parametrize("configured_value", [0, -1])
def test_non_positive_max_new_tokens_uses_default(configured_value):
    config = AgentContextParameters(max_new_tokens=configured_value)

    assert config.max_new_tokens == 4096


def test_configuration_manager_parses_max_new_tokens():
    manager = ConfigurationManager({"agent_context": {"max_new_tokens": 16384}})

    config = manager.parse_config(AgentContextParameters, "agent_context")

    assert config.max_new_tokens == 16384


def test_max_parallel_subagents_uses_builtin_default(monkeypatch):
    """Use the built-in limit when neither TOML nor the environment sets it."""
    monkeypatch.delenv("DBGPT_MAX_PARALLEL_SUBAGENTS", raising=False)

    config = AgentContextParameters()

    assert config.max_parallel_subagents == 3


def test_max_parallel_subagents_accepts_config_value(monkeypatch):
    """Keep the value parsed from the TOML configuration."""
    monkeypatch.delenv("DBGPT_MAX_PARALLEL_SUBAGENTS", raising=False)

    config = AgentContextParameters(max_parallel_subagents=5)

    assert config.max_parallel_subagents == 5


@pytest.mark.parametrize("configured_value", [0, -1])
def test_non_positive_max_parallel_subagents_config_uses_default(
    monkeypatch, configured_value
):
    """Prevent non-positive TOML values from disabling the dispatch tool."""
    monkeypatch.delenv("DBGPT_MAX_PARALLEL_SUBAGENTS", raising=False)

    config = AgentContextParameters(max_parallel_subagents=configured_value)

    assert config.max_parallel_subagents == 3


def test_configuration_manager_parses_max_parallel_subagents(monkeypatch):
    """Parse the field through the same configuration manager used at startup."""
    monkeypatch.delenv("DBGPT_MAX_PARALLEL_SUBAGENTS", raising=False)
    manager = ConfigurationManager({"agent_context": {"max_parallel_subagents": 5}})

    config = manager.parse_config(AgentContextParameters, "agent_context")

    assert config.max_parallel_subagents == 5


def test_max_parallel_subagents_environment_overrides_config(monkeypatch):
    """Let deployments override the TOML value with a direct environment variable."""
    monkeypatch.setenv("DBGPT_MAX_PARALLEL_SUBAGENTS", "4")

    config = AgentContextParameters(max_parallel_subagents=5)

    assert config.max_parallel_subagents == 4


def test_invalid_max_parallel_subagents_environment_keeps_config(monkeypatch):
    """Ignore invalid environment values instead of discarding valid TOML config."""
    monkeypatch.setenv("DBGPT_MAX_PARALLEL_SUBAGENTS", "invalid")

    config = AgentContextParameters(max_parallel_subagents=5)

    assert config.max_parallel_subagents == 5


@pytest.mark.parametrize("env_value", ["0", "-1"])
def test_non_positive_max_parallel_subagents_environment_keeps_config(
    monkeypatch, env_value
):
    """Ignore non-positive environment values instead of disabling dispatch."""
    monkeypatch.setenv("DBGPT_MAX_PARALLEL_SUBAGENTS", env_value)

    config = AgentContextParameters(max_parallel_subagents=5)

    assert config.max_parallel_subagents == 5
