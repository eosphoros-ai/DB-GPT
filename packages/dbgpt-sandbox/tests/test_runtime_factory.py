from unittest.mock import Mock

import pytest

from dbgpt_sandbox.sandbox.execution_layer import runtime_factory
from dbgpt_sandbox.sandbox.execution_layer.local_runtime import LocalRuntime


@pytest.fixture(autouse=True)
def clean_runtime_config(monkeypatch):
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", None)
    monkeypatch.setattr(
        LocalRuntime, "_detect_supported_languages", lambda _: ["python"]
    )


@pytest.mark.parametrize("setting", [None, "", " ", "local", "LOCAL"])
def test_unconfigured_runtime_is_local_even_with_docker_installed(monkeypatch, setting):
    docker = Mock(side_effect=AssertionError("Default must not probe Docker"))
    monkeypatch.setattr(runtime_factory, "DockerRuntime", docker)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", setting)
    assert isinstance(runtime_factory.RuntimeFactory.create(), LocalRuntime)
    docker.assert_not_called()


def test_local_does_not_require_an_additional_opt_in(monkeypatch):
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL_RUNTIME", "false")
    assert isinstance(runtime_factory.RuntimeFactory.create("local"), LocalRuntime)


def test_explicit_preference_overrides_environment(monkeypatch):
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "docker")
    docker = Mock(side_effect=AssertionError("Explicit local must override Docker"))
    monkeypatch.setattr(runtime_factory, "DockerRuntime", docker)
    assert isinstance(runtime_factory.RuntimeFactory.create("local"), LocalRuntime)


def test_configured_docker_checks_the_daemon(monkeypatch):
    docker = Mock()
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "docker")
    monkeypatch.setattr(runtime_factory, "DockerRuntime", Mock(return_value=docker))
    assert runtime_factory.RuntimeFactory.create() is docker
    docker.docker_client.ping.assert_called_once_with()


@pytest.mark.parametrize("error", [ImportError("no SDK"), OSError("no daemon")])
def test_missing_docker_falls_back_to_local(monkeypatch, caplog, error):
    monkeypatch.setattr(runtime_factory, "DockerRuntime", Mock(side_effect=error))
    assert isinstance(runtime_factory.RuntimeFactory.create("docker"), LocalRuntime)
    assert "using LocalRuntime" in caplog.text


def test_unreachable_daemon_closes_client_and_falls_back(monkeypatch):
    docker = Mock()
    docker.docker_client.ping.side_effect = OSError("offline")
    monkeypatch.setattr(runtime_factory, "DockerRuntime", Mock(return_value=docker))
    assert isinstance(runtime_factory.RuntimeFactory.create("docker"), LocalRuntime)
    docker.docker_client.close.assert_called_once_with()


@pytest.mark.parametrize("runtime", ["podman", "nerdctl"])
def test_missing_optional_runtime_falls_back(monkeypatch, runtime):
    monkeypatch.setattr(
        runtime_factory.EnvironmentDetector, f"is_{runtime}_available", lambda: False
    )
    assert isinstance(runtime_factory.RuntimeFactory.create(runtime), LocalRuntime)


def test_unknown_runtime_is_a_configuration_error():
    with pytest.raises(ValueError, match="Unknown sandbox runtime"):
        runtime_factory.RuntimeFactory.create("doker")
