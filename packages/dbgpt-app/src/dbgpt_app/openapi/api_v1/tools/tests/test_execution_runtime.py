"""Runtime policy, single-execution lifecycle, and actual local tool behavior."""

import asyncio
import json
import logging
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from dbgpt_app.openapi.api_v1.subagent.react_tools import make_react_tools
from dbgpt_app.openapi.api_v1.tools import _execution
from dbgpt_app.openapi.api_v1.tools.code_interpreter import make_code_interpreter
from dbgpt_app.openapi.api_v1.tools.shell_interpreter import make_shell_interpreter
from dbgpt_sandbox.sandbox.display_layer.display_layer import DisplayResult
from dbgpt_sandbox.sandbox.execution_layer import runtime_factory
from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionResult, ExecutionStatus
from dbgpt_sandbox.sandbox.execution_layer.local_runtime import LocalRuntime


@pytest.fixture(autouse=True)
def local_config(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", None)
    monkeypatch.setattr(
        LocalRuntime, "_detect_supported_languages", lambda _: ["python", "bash"]
    )
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH", str(tmp_path / "pilot")
    )
    monkeypatch.setattr(
        "dbgpt.configs.model_config.STATIC_MESSAGE_IMG_PATH", str(tmp_path / "images")
    )


def _fake_runtime(result=None, *, kind="docker", start_error=None):
    session = SimpleNamespace(
        execute=AsyncMock(return_value=result), collect_artifacts=AsyncMock()
    )
    return SimpleNamespace(
        runtime_id=kind,
        docker_client=Mock(),
        create_session=AsyncMock(return_value=session, side_effect=start_error),
        destroy_session=AsyncMock(),
        session=session,
    )


def _execution_logs(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == _execution.__name__
        and record.levelno == logging.INFO
        and record.getMessage().startswith("Sandbox execution:")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["local", "docker"])
@pytest.mark.parametrize("language", ["python", "bash"])
async def test_actual_runtime_is_logged_before_execution_without_sensitive_data(
    tmp_path, monkeypatch, caplog, kind, language
):
    caplog.set_level(logging.INFO, logger=_execution.__name__)
    runtime = _fake_runtime(kind=kind)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", Mock(return_value=runtime))

    async def execute(code):
        session_id = runtime.create_session.call_args.args[0]
        assert _execution_logs(caplog) == [
            f"Sandbox execution: runtime={kind} language={language} "
            f"session_id={session_id}"
        ]
        return ExecutionResult(ExecutionStatus.SUCCESS)

    runtime.session.execute.side_effect = execute
    await _execution.run_code(
        "SENSITIVE_CODE_SENTINEL",
        language=language,
        work_dir=str(tmp_path),
        env={"PRIVATE_VALUE": "SENSITIVE_ENV_SENTINEL"},
    )
    assert len(_execution_logs(caplog)) == 1
    assert "SENSITIVE_CODE_SENTINEL" not in caplog.text
    assert "SENSITIVE_ENV_SENTINEL" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["docker", "podman", "nerdctl"])
@pytest.mark.parametrize("language", ["python", "bash"])
@pytest.mark.parametrize(
    "start_error",
    [
        RuntimeError("image missing"),
        FileNotFoundError("input missing"),
        ValueError("symlink upload rejected"),
        PermissionError("input access denied"),
    ],
)
async def test_container_session_failure_does_not_execute_or_retry_locally(
    tmp_path, monkeypatch, caplog, kind, language, start_error
):
    """Setup and input-upload failures stop execution and still clean up."""
    caplog.set_level(logging.INFO, logger=_execution.__name__)
    runtime = _fake_runtime(kind=kind, start_error=start_error)
    local = _fake_runtime(
        ExecutionResult(ExecutionStatus.SUCCESS, output="ok"), kind="local"
    )
    create = Mock(side_effect=[runtime, local])
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)

    with pytest.raises(type(start_error)) as exc:
        await _execution.run_code("print(1)", language=language, work_dir=str(tmp_path))

    assert exc.value is start_error
    create.assert_called_once_with()
    runtime.session.execute.assert_not_called()
    runtime.session.collect_artifacts.assert_not_called()
    runtime.destroy_session.assert_awaited_once_with(
        runtime.create_session.call_args.args[0]
    )
    if kind == "docker":
        runtime.docker_client.close.assert_called_once_with()
    local.create_session.assert_not_called()
    local.session.execute.assert_not_called()
    assert _execution_logs(caplog) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("subagent", [False, True])
@pytest.mark.parametrize("tool_name", ["code_interpreter", "shell_interpreter"])
@pytest.mark.parametrize("failure_stage", ["runtime", "session"])
async def test_agent_tools_surface_setup_failure_without_local_execution(
    tmp_path, monkeypatch, subagent, tool_name, failure_stage
):
    """Main and sub-agent tools return an error instead of executing locally."""
    error = RuntimeError("configured container unavailable")
    runtime = _fake_runtime(start_error=error)
    create = Mock(
        return_value=runtime,
        side_effect=error if failure_stage == "runtime" else None,
    )
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)
    state = {"conv_id": "container-error"}
    if subagent:
        tool = make_react_tools(state)[tool_name]
    else:
        factory = (
            make_code_interpreter
            if tool_name == "code_interpreter"
            else make_shell_interpreter
        )
        tool = factory(state)

    output = json.loads(await tool(code="print(1)"))

    text = "\n".join(
        chunk["content"] for chunk in output["chunks"] if chunk["output_type"] == "text"
    )
    assert "configured container unavailable" in text
    create.assert_called_once_with()
    runtime.session.execute.assert_not_called()
    assert not list((tmp_path / "pilot").rglob("_run_*.py"))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["success", "error", "timeout"])
async def test_display_result_is_normalized_without_replay(
    tmp_path, monkeypatch, status
):
    runtime = _fake_runtime(
        DisplayResult(status, "stdout", "stderr", 1.0, 0 if status == "success" else 1)
    )
    create = Mock(return_value=runtime)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)
    result = await _execution.run_code(
        "code", language="python", work_dir=str(tmp_path)
    )
    assert result.status == ExecutionStatus(status)
    assert result.output == "stdout"
    create.assert_called_once_with()
    runtime.session.execute.assert_awaited_once()
    runtime.session.collect_artifacts.assert_awaited_once()
    runtime.destroy_session.assert_awaited_once()
    runtime.docker_client.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_execution_exception_never_replays_locally(tmp_path, monkeypatch):
    runtime = _fake_runtime()
    runtime.session.execute.side_effect = RuntimeError("execution disconnected")
    create = Mock(return_value=runtime)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)
    with pytest.raises(RuntimeError, match="execution disconnected"):
        await _execution.run_code("code", language="bash", work_dir=str(tmp_path))
    create.assert_called_once_with()
    runtime.destroy_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_artifact_failure_keeps_stdout_and_does_not_replay(tmp_path, monkeypatch):
    runtime = _fake_runtime(ExecutionResult(ExecutionStatus.SUCCESS, output="ran once"))
    runtime.session.collect_artifacts.side_effect = OSError("download failed")
    create = Mock(return_value=runtime)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)
    result = await _execution.run_code(
        "code", language="python", work_dir=str(tmp_path)
    )
    assert result.status == ExecutionStatus.ERROR
    assert result.output == "ran once"
    assert "download failed" in result.error
    create.assert_called_once_with()
    runtime.destroy_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_cleans_up_without_replay(tmp_path, monkeypatch):
    entered = asyncio.Event()

    async def execute(_):
        entered.set()
        await asyncio.Event().wait()

    runtime = _fake_runtime()
    runtime.session.execute.side_effect = execute
    create = Mock(return_value=runtime)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)
    task = asyncio.create_task(
        _execution.run_code("code", language="python", work_dir=str(tmp_path))
    )
    await asyncio.wait_for(entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    runtime.destroy_session.assert_awaited_once()
    create.assert_called_once_with()


@pytest.mark.asyncio
async def test_files_and_workspace_reach_the_selected_runtime(tmp_path, monkeypatch):
    file_path = tmp_path / 'quote";name.csv'
    file_path.write_text("x\n1\n")
    mapping = tmp_path / "files.json"
    mapping.write_text(json.dumps({"sf_1": str(file_path)}))
    runtime = _fake_runtime(ExecutionResult(ExecutionStatus.SUCCESS))
    monkeypatch.setattr(_execution.RuntimeFactory, "create", Mock(return_value=runtime))
    await _execution.run_code(
        "print(FILE_PATH)",
        language="python",
        work_dir=str(tmp_path / "work"),
        env={"FILE_PATH": str(file_path), "FILES_JSON": str(mapping)},
    )
    config = runtime.create_session.call_args.args[1]
    assert config.host_working_dir == str(tmp_path / "work")
    assert set(config.input_files) == {str(file_path), str(mapping)}
    assert config.environment_vars["FILE_PATH"] == str(file_path)
    assert config.validate_code is False


@pytest.mark.asyncio
async def test_local_python_uses_app_interpreter_and_preserves_file_io(tmp_path):
    result = await _execution.run_code(
        "import sys, os\nfrom pathlib import Path\nprint(sys.executable)\n"
        'Path("output.txt").write_text(os.environ["TOOL_VALUE"])',
        language="python",
        work_dir=str(tmp_path),
        env={"TOOL_VALUE": "ok"},
    )
    assert result.status == ExecutionStatus.SUCCESS, result.error
    assert result.output.strip() == sys.executable
    assert (tmp_path / "output.txt").read_text() == "ok"
    assert "TOOL_VALUE" not in os.environ


@pytest.mark.asyncio
async def test_parallel_local_sessions_do_not_mutate_parent_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TOOL_VALUE", "parent")
    results = await asyncio.gather(
        *(
            _execution.run_code(
                'import os, time\ntime.sleep(0.02)\nprint(os.environ["TOOL_VALUE"])',
                language="python",
                work_dir=str(tmp_path / name),
                env={"TOOL_VALUE": name},
            )
            for name in ("first", "second")
        )
    )
    assert [r.output.strip() for r in results] == ["first", "second"]
    assert os.environ["TOOL_VALUE"] == "parent"


@pytest.mark.asyncio
async def test_local_shell_executes_pipeline_and_preserves_artifact(tmp_path):
    result = await _execution.run_code(
        "printf 'hello' | tr '[:lower:]' '[:upper:]' | tee artifact.txt",
        language="bash",
        work_dir=str(tmp_path),
    )
    assert result.status == ExecutionStatus.SUCCESS, result.error
    assert result.output == "HELLO"
    assert (tmp_path / "artifact.txt").read_text() == "HELLO"


@pytest.mark.asyncio
@pytest.mark.parametrize("subagent", [False, True])
async def test_main_and_subagent_python_analyze_upload_and_return_image(
    tmp_path, subagent
):
    source = tmp_path / "sales.csv"
    source.write_text("sales\n2\n3\n")
    state = {"conv_id": "analysis", "file_path": str(source)}
    tool = (
        make_react_tools(state)["code_interpreter"]
        if subagent
        else make_code_interpreter(state)
    )
    output = json.loads(
        await tool(
            code="df = pd.read_csv(FILE_PATH)\nprint(int(df.sales.sum()))\n"
            'import matplotlib\nmatplotlib.use("Agg")\n'
            "import matplotlib.pyplot as plt\n"
            'plt.plot(df.sales)\nplt.savefig(os.path.join(PLOT_DIR, "chart.png"))'
        )
    )
    assert any(
        c["output_type"] == "text" and c["content"] == "5" for c in output["chunks"]
    ), output
    images = [c["content"] for c in output["chunks"] if c["output_type"] == "image"]
    assert len(images) == 1
    assert state["generated_images"] == images
    assert (tmp_path / "images" / images[0].split("/")[-1]).is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize("subagent", [False, True])
async def test_main_and_subagent_shell_use_configured_factory(
    tmp_path, monkeypatch, subagent
):
    runtime = _fake_runtime(DisplayResult("success", "from container", "", 0, 0))
    create = Mock(return_value=runtime)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", create)
    state = {"conv_id": "shell"}
    tool = (
        make_react_tools(state)["shell_interpreter"]
        if subagent
        else make_shell_interpreter(state)
    )
    output = json.loads(await tool(code="echo test"))
    assert {"output_type": "text", "content": "from container"} in output["chunks"]
    assert runtime.create_session.call_args.args[1].language == "bash"
    create.assert_called_once_with()


@pytest.mark.asyncio
async def test_real_local_timeout_stops_the_child(tmp_path):
    import psutil

    pid_path = tmp_path / "child.pid"
    result = await _execution.run_code(
        "import os, time\nfrom pathlib import Path\n"
        'Path("child.pid").write_text(str(os.getpid()))\ntime.sleep(30)',
        language="python",
        work_dir=str(tmp_path),
        timeout=0.2,
    )
    assert result.status == ExecutionStatus.TIMEOUT
    assert pid_path.exists()
    assert not psutil.pid_exists(int(pid_path.read_text()))
