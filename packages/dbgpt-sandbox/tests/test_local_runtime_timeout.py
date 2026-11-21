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

# A child in its own session leaves a re-parented grandchild in that new
# group: neither the script's group kill nor a children() walk reaches it.
NEW_SESSION_GRANDCHILD = """
import os, subprocess, sys
subprocess.Popen([sys.executable, "-c", '''
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
'''], start_new_session=True)
import time
time.sleep(60)
"""

# The script exits at once, but its child keeps the captured stdout open, so
# the execution still times out after the script itself is gone.
EXITED_SCRIPT = """
import os, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", '''
import os, time
time.sleep(3)
open(os.environ["LATE_FILE"], "w").close()
time.sleep(60)
'''])
with open(os.environ["PID_FILE"] + ".tmp", "w") as handle:
    handle.write(str(child.pid))
os.rename(os.environ["PID_FILE"] + ".tmp", os.environ["PID_FILE"])
"""


def _alive(pid: int) -> bool:
    """Return whether ``pid`` is running (a zombie counts as stopped)."""
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


async def _wait_until_dead(pid: int, limit: float = 5) -> None:
    """Poll until ``pid`` stops or ``limit`` seconds pass."""
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
    [DETACHED_GRANDCHILD, NEW_SESSION_CHILD, NEW_SESSION_GRANDCHILD, EXITED_SCRIPT],
    ids=[
        "reparented-grandchild",
        "new-session-child",
        "new-session-grandchild",
        "exited-script",
    ],
)
async def test_timeout_kills_every_descendant(tmp_path, code):
    """A timeout leaves no descendant running, wherever it ended up."""
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
    """Stopping a session mid-execution also stops re-parented descendants."""
    session = _session(tmp_path, timeout=10)
    assert await session.start()
    pid_file = tmp_path / "descendant.pid"
    task = asyncio.create_task(session.execute(DETACHED_GRANDCHILD))
    pid = None
    try:
        deadline = asyncio.get_running_loop().time() + 5
        while not pid_file.exists() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
        assert pid_file.exists(), "descendant did not record its pid in time"
        pid = int(pid_file.read_text())

        assert await session.stop()
        await _wait_until_dead(pid)
        assert not _alive(pid)
        await asyncio.wait_for(task, 5)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if pid is not None and _alive(pid):
            os.kill(pid, signal.SIGKILL)


class _FakeDescendant:
    def __init__(self, pid, events, error=None, suspend_error=None, running=True):
        self.pid = pid
        self._events = events
        self._error = error
        self._suspend_error = suspend_error
        self._running = running

    def suspend(self):
        self._events.append(("suspend", self.pid))
        if self._suspend_error:
            raise self._suspend_error

    def is_running(self):
        return self._running

    def kill(self):
        self._events.append(("kill", self.pid))
        if self._error:
            raise self._error


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_cleanup_freezes_group_and_survives_denied_kill(monkeypatch):
    """Freeze, snapshot, kill; a denied descendant kill does not stop cleanup."""
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
    # 12 left the group with setsid and leads its own group.
    monkeypatch.setattr(
        local_runtime.os, "getpgid", lambda pid: 10 if pid == 11 else pid
    )

    def wait_procs(procs, timeout):
        events.append(("reap", tuple(p.pid for p in procs)))
        return list(procs), []

    monkeypatch.setattr(local_runtime.psutil, "wait_procs", wait_procs)

    local_runtime._kill_session_leader(10)

    assert events == [
        # No group member can fork a new session after the snapshot.
        ("killpg", 10, signal.SIGSTOP),
        ("snapshot",),
        # The group stop misses descendants that called setsid.
        ("suspend", 11),
        ("suspend", 12),
        ("killpg", 10, signal.SIGKILL),
        ("kill", 11),
        # 12 is killed with its own group, which the snapshot may not cover.
        ("killpg", 12, signal.SIGKILL),
        ("kill", 12),
        ("reap", (11, 12)),
    ]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_cleanup_never_signals_a_reused_group_id(monkeypatch):
    """A leader whose PID may have been reused is not group-killed."""
    events = []
    descendants = [
        # Stopped and led its own group, but its PID now names another process.
        _FakeDescendant(12, events, running=False),
        # Could not be stopped, so it may exit and its PID be reused.
        _FakeDescendant(13, events, suspend_error=psutil.AccessDenied(13)),
    ]

    class FakeProcess:
        def __init__(self, pid):
            pass

        def children(self, recursive):
            return descendants

    monkeypatch.setattr(local_runtime.psutil, "Process", FakeProcess)
    monkeypatch.setattr(
        local_runtime.os,
        "killpg",
        lambda pgid, signum: events.append(("killpg", pgid, signum)),
        raising=False,
    )
    monkeypatch.setattr(local_runtime.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        local_runtime.psutil, "wait_procs", lambda procs, timeout: (list(procs), [])
    )

    local_runtime._kill_session_leader(10)

    group_kills = [e for e in events if e[0] == "killpg"]
    assert group_kills == [
        ("killpg", 10, signal.SIGSTOP),
        ("killpg", 10, signal.SIGKILL),
    ]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_cleanup_kills_group_when_snapshot_fails(monkeypatch):
    """A failed descendant scan (e.g. hidepid) must not leave the group stopped."""
    signals = []

    class FakeProcess:
        def __init__(self, pid):
            pass

        def children(self, recursive):
            raise PermissionError("hidepid")

    monkeypatch.setattr(local_runtime.psutil, "Process", FakeProcess)
    monkeypatch.setattr(
        local_runtime.os,
        "killpg",
        lambda pgid, signum: signals.append(signum),
        raising=False,
    )

    local_runtime._kill_session_leader(10)

    assert signals == [signal.SIGSTOP, signal.SIGKILL]
