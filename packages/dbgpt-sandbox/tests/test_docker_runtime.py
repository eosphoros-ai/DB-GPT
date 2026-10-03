"""Container execution and workspace transfer tests without a Docker daemon."""

import asyncio
import io
import tarfile
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from dbgpt_sandbox.sandbox.execution_layer.base import SessionConfig
from dbgpt_sandbox.sandbox.execution_layer.docker_runtime import (
    DockerRuntime,
    DockerSandboxSession,
)


def _container():
    return SimpleNamespace(
        exec_run=Mock(return_value=SimpleNamespace(exit_code=0, output=(b"ok", b""))),
        put_archive=Mock(return_value=True),
        get_archive=Mock(),
        remove=Mock(),
        kill=Mock(),
    )


def _archive(entries):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as tar:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
            else:
                info.type = tarfile.SYMTYPE
                info.linkname = content
                tar.addfile(info)
    return data.getvalue()


@pytest.mark.asyncio
async def test_start_uses_custom_image_and_explicit_archive_inputs(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "state.txt").write_text("previous result")
    source = tmp_path / 'input";name.csv'
    source.write_text("x\n1\n")
    container = _container()
    uploaded = []

    def put_archive(path, archive):
        with tarfile.open(fileobj=archive) as tar:
            uploaded.append((path, tar.getnames()))
        return True

    container.put_archive.side_effect = put_archive
    client = SimpleNamespace(
        containers=SimpleNamespace(run=Mock(return_value=container))
    )
    config = SessionConfig(
        language="python",
        working_dir=str(work),
        host_working_dir=str(work),
        input_files=[str(source)],
        image="test-agent-image",
        max_cpus=2,
    )
    session = DockerSandboxSession("transfer", config, client)
    assert await session.start()
    options = client.containers.run.call_args.kwargs
    assert options["image"] == "test-agent-image"
    assert options["nano_cpus"] == 2_000_000_000
    assert "volumes" not in options
    assert (str(tmp_path), ["work", "work/state.txt"]) in uploaded
    assert (str(tmp_path), [source.name]) in uploaded
    await session.stop()
    container.remove.assert_called_once_with(force=True)


@pytest.mark.asyncio
async def test_bash_is_executed_not_printed(tmp_path):
    container = _container()
    session = DockerSandboxSession("bash", SessionConfig(language="bash"), None)
    session.container = container
    session._is_active = True
    result = await session.execute("printf hello")
    assert result.status == "success"
    commands = [c.args[0] for c in container.exec_run.call_args_list]
    assert any(
        isinstance(c, str) and c.startswith("bash ") and c.endswith(".sh")
        for c in commands
    )


@pytest.mark.asyncio
async def test_timeout_kills_code_and_does_not_block_event_loop():
    container = _container()
    released = threading.Event()
    entered = threading.Event()

    def execute(*args, **kwargs):
        if kwargs.get("demux"):
            entered.set()
            released.wait(timeout=3)
        return SimpleNamespace(exit_code=0, output=(b"", b""))

    container.exec_run.side_effect = execute
    container.kill.side_effect = released.set
    session = DockerSandboxSession("timeout", SessionConfig(timeout=0.1), None)
    session.container = container
    session._is_active = True
    try:
        result = await session.execute("print(1)")
        assert entered.is_set()
        assert result.status == "timeout"
        container.kill.assert_called_once_with()
        assert not session.is_active
    finally:
        released.set()


@pytest.mark.asyncio
async def test_cancelled_execution_kills_container():
    container = _container()
    entered = threading.Event()
    released = threading.Event()

    def execute(*args, **kwargs):
        if kwargs.get("demux"):
            entered.set()
            released.wait(timeout=3)
        return SimpleNamespace(exit_code=0, output=(b"", b""))

    container.exec_run.side_effect = execute
    container.kill.side_effect = released.set
    session = DockerSandboxSession("cancel", SessionConfig(), None)
    session.container = container
    session._is_active = True
    task = asyncio.create_task(session.execute("print(1)"))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        container.kill.assert_called_once_with()
    finally:
        released.set()


def _session_for_download(tmp_path, entries):
    work = tmp_path / "work"
    work.mkdir()
    container = _container()
    container.get_archive.return_value = ([_archive(entries)], {})
    session = DockerSandboxSession(
        "download", SessionConfig(working_dir="/work", host_working_dir=str(work)), None
    )
    session.container = container
    return session, work


@pytest.mark.asyncio
async def test_artifacts_are_copied_back_before_container_removal(tmp_path):
    session, work = _session_for_download(
        tmp_path,
        [
            ("work/chart.png", b"image-bytes", "file"),
            ("work/nested/result.csv", b"x\n1\n", "file"),
            ("work/link", "/etc/passwd", "link"),
        ],
    )
    await session.collect_artifacts()
    assert (work / "chart.png").read_bytes() == b"image-bytes"
    assert (work / "nested/result.csv").read_text() == "x\n1\n"
    assert not (work / "link").exists()
    session.container.remove.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/absolute.txt", "work/../../escape", "other/file"])
async def test_artifact_archive_cannot_escape_workspace(tmp_path, path):
    session, _ = _session_for_download(tmp_path, [(path, b"bad", "file")])
    with pytest.raises(ValueError):
        await session.collect_artifacts()
    assert not (tmp_path / "escape").exists()


@pytest.mark.asyncio
async def test_artifacts_cannot_follow_existing_host_symlink(tmp_path):
    session, work = _session_for_download(
        tmp_path, [("work/link/file", b"bad", "file")]
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (work / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes workspace"):
        await session.collect_artifacts()
    assert not (outside / "file").exists()


@pytest.mark.asyncio
async def test_destroy_awaits_session_cleanup():
    runtime = object.__new__(DockerRuntime)
    session = SimpleNamespace(stop=AsyncMock(return_value=True))
    runtime.sessions = {"session": session}
    assert await runtime.destroy_session("session")
    session.stop.assert_awaited_once_with()
    assert not runtime.sessions


@pytest.mark.asyncio
async def test_cancelled_creation_recovers_and_removes_container():
    container = _container()
    entered = threading.Event()
    released = threading.Event()

    def create(**kwargs):
        entered.set()
        released.wait(timeout=3)
        return container

    runtime = object.__new__(DockerRuntime)
    runtime.sessions = {}
    runtime.docker_client = SimpleNamespace(containers=SimpleNamespace(run=create))
    task = asyncio.create_task(runtime.create_session("cancel-create", SessionConfig()))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        # Let the cancellation handler run before the SDK call returns.
        await asyncio.sleep(0)
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        container.remove.assert_called_once_with(force=True)
        assert runtime.sessions == {}
    finally:
        released.set()
