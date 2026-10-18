"""Keep explicitly configured CLI backends compatible with agent workspaces."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dbgpt_sandbox.sandbox.execution_layer import nerdctl_runtime, podman_runtime
from dbgpt_sandbox.sandbox.execution_layer.base import SessionConfig


@pytest.fixture(
    params=[
        (podman_runtime, "PodmanSandboxSession", "PodmanRuntime"),
        (nerdctl_runtime, "NerdctlSandboxSession", "NerdctlRuntime"),
    ]
)
def backend(request):
    return request.param


@pytest.mark.asyncio
async def test_cli_agent_mounts_only_workspace_and_explicit_inputs(
    backend, monkeypatch, tmp_path
):
    module, session_name, _ = backend
    command = AsyncMock(return_value=(0, "", ""))
    monkeypatch.setattr(module, "_run_cmd", command)
    work = tmp_path / "work"
    work.mkdir()
    external = tmp_path / "input.csv"
    external.write_text("x\n1\n")
    config = SessionConfig(
        language="bash",
        working_dir=str(work),
        host_working_dir=str(work),
        input_files=[str(external), str(work / "inside.csv")],
        image="custom-agent-image",
    )
    session = getattr(module, session_name)("test", config)
    assert await session.start()
    args = command.call_args_list[0].args[0]
    mounts = [args[index + 1] for index, arg in enumerate(args) if arg == "-v"]
    assert mounts == [f"{work}:{work}:rw", f"{external}:{external}:ro"]
    assert "custom-agent-image" in args
    assert session._get_exec_command("script.sh") == "bash script.sh"


@pytest.mark.asyncio
async def test_cli_cleanup_is_awaited(backend):
    module, _, runtime_name = backend
    runtime = object.__new__(getattr(module, runtime_name))
    session = SimpleNamespace(stop=AsyncMock(return_value=True))
    runtime.sessions = {"test": session}
    assert await runtime.destroy_session("test")
    session.stop.assert_awaited_once_with()
    assert not runtime.sessions


@pytest.mark.asyncio
async def test_failed_cli_session_is_cleaned_before_error(backend, monkeypatch):
    module, session_name, runtime_name = backend
    session = SimpleNamespace(start=AsyncMock(return_value=False), stop=AsyncMock())
    monkeypatch.setattr(module, session_name, lambda *args: session)
    runtime = object.__new__(getattr(module, runtime_name))
    runtime.sessions = {}
    with pytest.raises(RuntimeError):
        await runtime.create_session("test", SessionConfig())
    session.stop.assert_awaited_once_with()
    assert runtime.sessions == {}
