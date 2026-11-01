"""Local Python children must share the launching checkout's import paths."""

import os

import pytest

from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionStatus, SessionConfig
from dbgpt_sandbox.sandbox.execution_layer.local_runtime import LocalSandboxSession


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_path", [False, True])
async def test_python_imports_follow_parent_unless_session_overrides(
    tmp_path, monkeypatch, explicit_path
):
    active = tmp_path / "active checkout"
    installed = tmp_path / "other checkout"
    active.mkdir()
    installed.mkdir()
    (active / "checkout_probe.py").write_text("SOURCE = 'active'", encoding="utf-8")
    (installed / "checkout_probe.py").write_text("SOURCE = 'other'", encoding="utf-8")
    monkeypatch.syspath_prepend(str(active))
    monkeypatch.setenv("PYTHONPATH", str(installed))
    environment = {"PYTHONPATH": str(installed)} if explicit_path else {}
    session = LocalSandboxSession(
        "import-path-test",
        SessionConfig(
            language="python",
            working_dir=str(tmp_path / "execution"),
            environment_vars=environment,
            validate_code=False,
        ),
    )
    assert await session.start()
    try:
        result = await session.execute(
            "import checkout_probe; print(checkout_probe.SOURCE)"
        )
        assert result.status == ExecutionStatus.SUCCESS, result.error
        assert result.output.strip() == ("other" if explicit_path else "active")
        assert os.environ["PYTHONPATH"] == str(installed)
    finally:
        await session.stop()
