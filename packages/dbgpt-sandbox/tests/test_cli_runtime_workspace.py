"""Keep explicitly configured CLI backends compatible with agent workspaces."""

import asyncio
import contextlib
import sys
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


_SLEEP = "import time; time.sleep(60)"
# Writes until killed, so stdout is still full when ``_run_cmd`` is interrupted.
_FLOOD = "import os\nwhile True: os.write(1, b'x' * 65536)"


async def _start_cli_command(module, monkeypatch, code=_SLEEP, timeout=None):
    """Run a long-lived command through ``_run_cmd`` and return its process."""
    spawn = asyncio.create_subprocess_exec
    spawned = []
    started = asyncio.Event()

    async def record_spawn(*args, **kwargs):
        proc = await spawn(*args, **kwargs)
        spawned.append(proc)
        started.set()
        return proc

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", record_spawn)
    task = asyncio.create_task(
        module._run_cmd([sys.executable, "-c", code], timeout=timeout)
    )
    await started.wait()
    return task, spawned[0]


@pytest.mark.asyncio
async def test_cli_command_is_killed_when_request_is_cancelled(backend, monkeypatch):
    module, _, _ = backend
    task, proc = await _start_cli_command(module, monkeypatch)
    try:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Killed and reaped by _run_cmd, not left running after the request.
        assert proc.returncode is not None
    finally:
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()


@pytest.mark.asyncio
async def test_cli_command_is_killed_on_timeout(backend, monkeypatch):
    module, _, _ = backend
    task, proc = await _start_cli_command(module, monkeypatch, timeout=0.1)
    try:
        with pytest.raises(asyncio.TimeoutError):
            await task
        assert proc.returncode is not None
    finally:
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
async def test_cli_cleanup_does_not_hang_on_full_pipes(backend, monkeypatch, interrupt):
    module, _, _ = backend
    timeout = 0.5 if interrupt == "timeout" else None
    task, proc = await _start_cli_command(
        module, monkeypatch, code=_FLOOD, timeout=timeout
    )
    try:
        if interrupt == "cancel":
            await asyncio.sleep(0.5)
            task.cancel()
        expected = (
            asyncio.CancelledError if interrupt == "cancel" else asyncio.TimeoutError
        )
        done, _ = await asyncio.wait({task}, timeout=10)
        assert task in done, "_run_cmd did not return after killing the process"
        with pytest.raises(expected):
            task.result()
        assert proc.returncode is not None
    finally:
        if not task.done():
            task.cancel()
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
