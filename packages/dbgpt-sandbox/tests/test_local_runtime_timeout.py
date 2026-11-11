"""A local execution timeout must stop every process the script started."""

import asyncio
import os
import signal

import psutil
import pytest

from dbgpt_sandbox.sandbox.execution_layer import local_runtime
from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionStatus, SessionConfig
from dbgpt_sandbox.sandbox.execution_layer.local_runtime import LocalSandboxSession

# The middle process exits without being reaped, so the grandchild is
# re-parented away from the script and a children() walk cannot reach it.
# The grandchild writes LATE_FILE one second after the 2s timeout.
DETACHED_GRANDCHILD = """
import os, time
if os.fork() == 0:
    if os.fork() == 0:
        with open(os.environ["PID_FILE"] + ".tmp", "w") as handle:
            handle.write(str(os.getpid()))
        os.rename(os.environ["PID_FILE"] + ".tmp", os.environ["PID_FILE"])
        time.sleep(3)
        open(os.environ["LATE_FILE"], "w").close()
        time.sleep(60)
    os._exit(0)
time.sleep(60)
"""

# A child that moved into its own session is outside the script's group.
NEW_SESSION_CHILD = """
import os, subprocess, sys, time
child = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
)
with open(os.environ["PID_FILE"] + ".tmp", "w") as handle:
    handle.write(str(child.pid))
os.rename(os.environ["PID_FILE"] + ".tmp", os.environ["PID_FILE"])
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


async def _wait_until_dead(pid: int, limit: float = 5) -> None:
    deadline = asyncio.get_running_loop().time() + limit
    while _alive(pid) and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.05)


def _session(tmp_path, timeout=2):
    return LocalSandboxSession(
        "timeout-descendants",
        SessionConfig(
            language="python",
            working_dir=str(tmp_path / "execution"),
            environment_vars={
                "PID_FILE": str(tmp_path / "descendant.pid"),
                "LATE_FILE": str(tmp_path / "late"),
            },
            timeout=timeout,
            validate_code=False,
        ),
    )


async def _run_until_timeout(tmp_path, code):
    session = _session(tmp_path)
    assert await session.start()
    try:
        return await session.execute(code)
    finally:
        await session.stop()


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
@pytest.mark.parametrize(
    "code",
    [DETACHED_GRANDCHILD, NEW_SESSION_CHILD],
    ids=["reparented-grandchild", "new-session-child"],
)
async def test_timeout_kills_every_descendant(tmp_path, code):
    pid = None
    try:
        result = await _run_until_timeout(tmp_path, code)
        assert result.status == ExecutionStatus.TIMEOUT
        pid = int((tmp_path / "descendant.pid").read_text())
        await _wait_until_dead(pid)
        assert not _alive(pid)
        assert not (tmp_path / "late").exists()
    finally:
        if pid is not None and _alive(pid):
            os.kill(pid, signal.SIGKILL)


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
async def test_stop_kills_descendants_of_a_running_execution(tmp_path):
    session = _session(tmp_path, timeout=10)
    assert await session.start()
    pid_file = tmp_path / "descendant.pid"
    task = asyncio.create_task(session.execute(DETACHED_GRANDCHILD))
    pid = None
    try:
        deadline = asyncio.get_running_loop().time() + 5
        while not pid_file.exists() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
        pid = int(pid_file.read_text())

        assert await session.stop()
        await _wait_until_dead(pid)
        assert not _alive(pid)
        await asyncio.wait_for(task, 5)
    finally:
        task.cancel()
        if pid is not None and _alive(pid):
            os.kill(pid, signal.SIGKILL)


class _FakeDescendant:
    def __init__(self, pid, events, error=None):
        self.pid = pid
        self._events = events
        self._error = error

    def kill(self):
        self._events.append(("kill", self.pid))
        if self._error:
            raise self._error


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_cleanup_freezes_group_and_survives_denied_kill(monkeypatch):
    events = []
    descendants = [
        _FakeDescendant(11, events, psutil.AccessDenied(11)),
        _FakeDescendant(12, events),
    ]

    class FakeProcess:
        def __init__(self, pid):
            assert pid == 10

        def children(self, recursive):
            events.append(("snapshot",))
            return descendants

    monkeypatch.setattr(local_runtime.psutil, "Process", FakeProcess)
    monkeypatch.setattr(
        local_runtime.os,
        "killpg",
        lambda pgid, signum: events.append(("killpg", pgid, signum)),
        raising=False,
    )

    local_runtime._kill_session_leader(10)

    assert events == [
        # No group member can fork a new session after the snapshot.
        ("killpg", 10, signal.SIGSTOP),
        ("snapshot",),
        ("killpg", 10, signal.SIGKILL),
        ("kill", 11),
        ("kill", 12),
    ]
