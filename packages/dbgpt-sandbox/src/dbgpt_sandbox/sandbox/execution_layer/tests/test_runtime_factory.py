import pytest

from dbgpt_sandbox.sandbox import config
from dbgpt_sandbox.sandbox.execution_layer import runtime_factory


def _disable_container_runtimes(monkeypatch):
    monkeypatch.setattr(
        runtime_factory.EnvironmentDetector,
        "is_docker_sdk_available",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        runtime_factory.EnvironmentDetector,
        "is_podman_available",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        runtime_factory.EnvironmentDetector,
        "is_nerdctl_available",
        staticmethod(lambda: False),
    )


def test_sandbox_runtime_defaults_to_auto() -> None:
    assert config.SANDBOX_RUNTIME == "auto"


def test_auto_runtime_fails_closed_when_no_container_backend(monkeypatch) -> None:
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "auto")

    with pytest.raises(RuntimeError, match="No container sandbox runtime"):
        runtime_factory.RuntimeFactory.create()


def test_blank_runtime_env_fails_closed_when_no_container_backend(monkeypatch) -> None:
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "")

    with pytest.raises(RuntimeError, match="No container sandbox runtime"):
        runtime_factory.RuntimeFactory.create()


def test_explicit_unavailable_container_runtime_does_not_fallback_to_local(
    monkeypatch,
) -> None:
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "docker")

    with pytest.raises(RuntimeError, match="指定的运行时不可用: docker"):
        runtime_factory.RuntimeFactory.create()


def test_local_runtime_requires_explicit_opt_in(monkeypatch) -> None:
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "local")

    runtime = runtime_factory.RuntimeFactory.create()

    assert isinstance(runtime, runtime_factory.LocalRuntime)


def test_runtime_preference_parameter_still_allows_local_opt_in(monkeypatch) -> None:
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "auto")
    monkeypatch.delenv("SANDBOX_RUNTIME", raising=False)

    runtime = runtime_factory.RuntimeFactory.create(runtime_preference="local")

    assert isinstance(runtime, runtime_factory.LocalRuntime)
