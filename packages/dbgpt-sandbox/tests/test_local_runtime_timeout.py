"""A local execution timeout must stop every process the script started."""

import asyncio
import os
import signal

import psutil
import pytest

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


async def _run_until_timeout(tmp_path, code):
    session = LocalSandboxSession(
        "timeout-descendants",
        SessionConfig(
            language="python",
            working_dir=str(tmp_path / "execution"),
            environment_vars={
                "PID_FILE": str(tmp_path / "descendant.pid"),
                "LATE_FILE": str(tmp_path / "late"),
            },
            timeout=2,
            validate_code=False,
        ),
    )
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
        # Past the grandchild's late write; a survivor would have made it.
        await asyncio.sleep(2)
        assert not _alive(pid)
        assert not (tmp_path / "late").exists()
    finally:
        if pid is not None and _alive(pid):
            os.kill(pid, signal.SIGKILL)
