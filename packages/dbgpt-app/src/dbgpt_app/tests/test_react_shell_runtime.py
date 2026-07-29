import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.agentic_data_api import (
    _normalize_sandbox_execution_status,
    _shell_validation_error,
)
from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionStatus


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            SimpleNamespace(status=ExecutionStatus.SUCCESS, exit_code=0),
            ExecutionStatus.SUCCESS,
        ),
        (
            SimpleNamespace(status="success", exit_code=0),
            ExecutionStatus.SUCCESS,
        ),
        (
            SimpleNamespace(status="error", exit_code=124),
            ExecutionStatus.TIMEOUT,
        ),
        (
            SimpleNamespace(status="error", exit_code=1),
            ExecutionStatus.ERROR,
        ),
        (
            SimpleNamespace(status="unexpected", exit_code=1),
            ExecutionStatus.ERROR,
        ),
    ],
)
def test_normalize_sandbox_execution_status(result, expected):
    assert _normalize_sandbox_execution_status(result) == expected


def test_shell_validation_allows_benign_code():
    assert _shell_validation_error("printf 'hello\\n'") is None


def test_shell_validation_rejects_existing_dangerous_pattern():
    error = _shell_validation_error("rm -rf /")

    assert error is not None
    assert "代码安全检查失败" in error


def test_shell_interpreter_uses_runtime_factory_and_entry_validation():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "openapi"
        / "api_v1"
        / "agentic_data_api.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    shell_interpreter = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "shell_interpreter"
    )

    call_names = {
        ast.unparse(node.func)
        for node in ast.walk(shell_interpreter)
        if isinstance(node, ast.Call)
    }

    assert "RuntimeFactory.create" in call_names
    assert "LocalRuntime" not in call_names
    assert "_shell_validation_error" in call_names
