"""The local Bash runtime must honor the executable selected by PATH."""

import shutil

import pytest

from dbgpt_sandbox.sandbox.execution_layer import local_runtime
from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionStatus, SessionConfig


def test_bash_command_uses_resolved_executable(monkeypatch):
    chosen = "C:/configured tools/Git/bin/bash.exe"
    monkeypatch.setattr(local_runtime.shutil, "which", lambda name: chosen)
    session = local_runtime.LocalSandboxSession("test", SessionConfig(language="bash"))
    assert session._get_exec_command("C:/workspace with spaces/test.sh") == [
        chosen,
        "C:/workspace with spaces/test.sh",
    ]


@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("bash"), reason="Bash is not installed")
async def test_local_bash_executes_in_native_path_with_spaces(tmp_path):
    session = local_runtime.LocalSandboxSession(
        "bash-path",
        SessionConfig(
            language="bash",
            working_dir=str(tmp_path / "workspace with spaces"),
            environment_vars={"VALIDATION_VALUE": "path-selected-shell"},
        ),
    )
    assert await session.start()
    try:
        result = await session.execute('printf "%s" "$VALIDATION_VALUE"')
        assert result.status == ExecutionStatus.SUCCESS, result.error
        assert result.output == "path-selected-shell"
    finally:
        await session.stop()
