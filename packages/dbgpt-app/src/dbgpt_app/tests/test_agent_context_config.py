"""Tests for agent context configuration."""

import pytest

from dbgpt.util.configure.manager import ConfigurationManager
from dbgpt_app.config import AgentContextParameters


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
