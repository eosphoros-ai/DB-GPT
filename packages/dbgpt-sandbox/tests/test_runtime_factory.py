import pytest

from dbgpt_sandbox.sandbox.execution_layer import runtime_factory
from dbgpt_sandbox.sandbox.execution_layer.local_runtime import LocalRuntime


def _disable_container_runtimes(monkeypatch):
    detector = runtime_factory.EnvironmentDetector
    monkeypatch.setattr(
        detector, "is_docker_sdk_available", staticmethod(lambda: False)
    )
    monkeypatch.setattr(detector, "is_podman_available", staticmethod(lambda: False))
    monkeypatch.setattr(detector, "is_nerdctl_available", staticmethod(lambda: False))


def test_auto_runtime_fails_closed_without_container(monkeypatch):
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", None)
    monkeypatch.setattr(runtime_factory, "SANDBOX_ALLOW_LOCAL_RUNTIME", False)

    with pytest.raises(RuntimeError, match="No container sandbox runtime"):
        runtime_factory.RuntimeFactory.create()


def test_local_runtime_requires_explicit_opt_in(monkeypatch):
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_ALLOW_LOCAL_RUNTIME", False)

    with pytest.raises(RuntimeError, match="LocalRuntime executes code on the host"):
        runtime_factory.RuntimeFactory.create("local")


def test_local_runtime_can_be_enabled_explicitly(monkeypatch):
    _disable_container_runtimes(monkeypatch)
    monkeypatch.setattr(runtime_factory, "SANDBOX_ALLOW_LOCAL_RUNTIME", True)

    runtime = runtime_factory.RuntimeFactory.create("local")

    assert isinstance(runtime, LocalRuntime)
