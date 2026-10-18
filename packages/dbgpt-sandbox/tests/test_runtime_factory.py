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
@pytest.mark.parametrize("explicit_argument", [False, True])
def test_missing_docker_fails_closed(monkeypatch, error, explicit_argument):
    """A container selected by config or argument must never execute locally."""
    monkeypatch.setattr(runtime_factory, "DockerRuntime", Mock(side_effect=error))
    local = Mock(side_effect=AssertionError("Must not create LocalRuntime"))
    monkeypatch.setattr(runtime_factory, "LocalRuntime", local)
    if not explicit_argument:
        monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "docker")

    with pytest.raises(RuntimeError, match="docker.*refusing local execution") as exc:
        runtime_factory.RuntimeFactory.create("docker" if explicit_argument else None)

    assert exc.value.__cause__ is error
    local.assert_not_called()


@pytest.mark.parametrize("ping_error", [None, OSError("offline")])
@pytest.mark.parametrize("close_error", [None, OSError("close failed")])
def test_unreachable_daemon_closes_client_and_fails_closed(
    monkeypatch, ping_error, close_error
):
    """Failed health checks close the client, even when cleanup itself fails."""
    docker = Mock()
    docker.docker_client.ping.return_value = False
    docker.docker_client.ping.side_effect = ping_error
    docker.docker_client.close.side_effect = close_error
    monkeypatch.setattr(runtime_factory, "DockerRuntime", Mock(return_value=docker))
    local = Mock(side_effect=AssertionError("Must not create LocalRuntime"))
    monkeypatch.setattr(runtime_factory, "LocalRuntime", local)

    with pytest.raises(RuntimeError, match="docker.*refusing local execution") as exc:
        runtime_factory.RuntimeFactory.create("docker")

    if ping_error:
        assert exc.value.__cause__ is ping_error
    else:
        assert "did not respond to ping" in str(exc.value.__cause__)
    docker.docker_client.close.assert_called_once_with()
    local.assert_not_called()


@pytest.mark.parametrize("runtime", ["podman", "nerdctl"])
def test_missing_optional_runtime_fails_closed(monkeypatch, runtime):
    """Missing optional container CLIs fail without creating a local runtime."""
    monkeypatch.setattr(
        runtime_factory.EnvironmentDetector, f"is_{runtime}_available", lambda: False
    )
    local = Mock(side_effect=AssertionError("Must not create LocalRuntime"))
    monkeypatch.setattr(runtime_factory, "LocalRuntime", local)

    with pytest.raises(RuntimeError, match=f"{runtime}.*refusing local execution"):
        runtime_factory.RuntimeFactory.create(runtime)

    local.assert_not_called()


@pytest.mark.parametrize(
    "runtime, constructor", [("podman", "PodmanRuntime"), ("nerdctl", "NerdctlRuntime")]
)
def test_optional_runtime_initialization_failure_is_not_downgraded(
    monkeypatch, runtime, constructor
):
    """An installed CLI does not justify local execution on backend failure."""
    monkeypatch.setattr(
        runtime_factory.EnvironmentDetector, f"is_{runtime}_available", lambda: True
    )
    error = OSError("backend unavailable")
    monkeypatch.setattr(runtime_factory, constructor, Mock(side_effect=error))
    local = Mock(side_effect=AssertionError("Must not create LocalRuntime"))
    monkeypatch.setattr(runtime_factory, "LocalRuntime", local)

    with pytest.raises(
        RuntimeError, match=f"{runtime}.*refusing local execution"
    ) as exc:
        runtime_factory.RuntimeFactory.create(runtime)

    assert exc.value.__cause__ is error
    local.assert_not_called()


def test_unknown_runtime_is_a_configuration_error():
    with pytest.raises(ValueError, match="Unknown sandbox runtime"):
        runtime_factory.RuntimeFactory.create("doker")
