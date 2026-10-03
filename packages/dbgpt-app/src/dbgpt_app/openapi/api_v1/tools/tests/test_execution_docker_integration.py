"""Opt-in live Docker tests: set DBGPT_TEST_DOCKER_IMAGE to a built agent image."""

import json
import os
from unittest.mock import Mock

import pytest

from dbgpt_app.openapi.api_v1.tools import _execution
from dbgpt_app.openapi.api_v1.tools.code_interpreter import make_code_interpreter
from dbgpt_app.openapi.api_v1.tools.shell_interpreter import make_shell_interpreter
from dbgpt_sandbox.sandbox.execution_layer import runtime_factory
from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionStatus

pytestmark = pytest.mark.skipif(
    not os.getenv("DBGPT_TEST_DOCKER_IMAGE"),
    reason="Live Docker test image not configured",
)


@pytest.fixture
def docker_runtime(monkeypatch, tmp_path):
    import docker

    image = os.environ["DBGPT_TEST_DOCKER_IMAGE"]
    client = docker.from_env(timeout=10)
    client.ping()
    client.images.get(image)
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "docker")
    monkeypatch.setattr(_execution, "SANDBOX_AGENT_IMAGE", image)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH", str(tmp_path / "pilot")
    )
    monkeypatch.setattr(
        "dbgpt.configs.model_config.STATIC_MESSAGE_IMG_PATH", str(tmp_path / "images")
    )
    original = runtime_factory.RuntimeFactory.create
    selected = []

    def create(preference=None):
        runtime = original(preference)
        selected.append(runtime)
        assert runtime.runtime_id == "docker", (
            "Live test must never pass via local fallback"
        )
        return runtime

    spy = Mock(side_effect=create)
    monkeypatch.setattr(_execution.RuntimeFactory, "create", spy)
    yield client, spy, selected
    for runtime in selected:
        for session in list(runtime.sessions.values()):
            if getattr(session, "container", None):
                session.container.remove(force=True)
        runtime.docker_client.close()
    client.close()


@pytest.mark.asyncio
async def test_live_docker_python_files_json_plot_and_persistent_workspace(
    tmp_path, docker_runtime
):
    _, create, selected = docker_runtime
    source = tmp_path / 'sales";name.csv'
    source.write_text("sales\n2\n3\n")
    files = tmp_path / "files.json"
    files.write_text(json.dumps({"sf_sales": str(source)}))
    outside = tmp_path / "not-an-input.txt"
    outside.write_text("host-only")
    state = {
        "conv_id": "docker-python",
        "file_path": str(source),
        "files_json_path": str(files),
    }
    tool = make_code_interpreter(state)
    chunks = json.loads(
        await tool(
            code=(
                "from pathlib import Path\n"
                "mapping = json.loads(Path(FILES_JSON).read_text())\n"
                'print(int(pd.read_csv(mapping["sf_sales"]).sales.sum()))\n'
                f'print("outside-visible", Path({str(outside)!r}).exists())\n'
                "import matplotlib.pyplot as plt\nplt.plot([1,2])\n"
                'plt.savefig(os.path.join(PLOT_DIR, "chart.png"))\n'
                'Path("result.txt").write_text("persistent")'
            )
        )
    )["chunks"]
    assert any(
        c["output_type"] == "text" and "5\noutside-visible False" in c["content"]
        for c in chunks
    ), chunks
    images = [c["content"] for c in chunks if c["output_type"] == "image"]
    assert len(images) == 1
    assert (tmp_path / "images" / images[0].split("/")[-1]).is_file()
    second = json.loads(
        await tool(
            code='from pathlib import Path; print(Path("result.txt").read_text())'
        )
    )
    assert {"output_type": "text", "content": "persistent"} in second["chunks"]
    assert create.call_count == 2
    assert all(not runtime.sessions for runtime in selected)


@pytest.mark.asyncio
async def test_live_docker_shell_pipeline_and_output_file(
    tmp_path, docker_runtime, monkeypatch
):
    monkeypatch.setattr(
        "dbgpt.configs.model_config.SKILLS_DIR", str(tmp_path / "no-skills")
    )
    tool = make_shell_interpreter({"conv_id": "docker-shell"})
    chunks = json.loads(
        await tool(code="printf hello | tr '[:lower:]' '[:upper:]' | tee result.txt")
    )["chunks"]
    assert {"output_type": "text", "content": "HELLO"} in chunks, chunks
    assert (tmp_path / "pilot/tmp/docker-shell/result.txt").read_text() == "HELLO"
    docker_runtime[1].assert_called_once_with()


@pytest.mark.asyncio
async def test_live_docker_timeout_removes_container_without_replay(
    tmp_path, docker_runtime
):
    result = await _execution.run_code(
        "import time; time.sleep(30)",
        language="python",
        work_dir=str(tmp_path / "timeout"),
        timeout=0.2,
    )
    assert result.status == ExecutionStatus.TIMEOUT, result
    docker_runtime[1].assert_called_once_with()
    assert all(not runtime.sessions for runtime in docker_runtime[2])


@pytest.mark.asyncio
async def test_live_docker_execution_error_never_falls_back(tmp_path, docker_runtime):
    result = await _execution.run_code(
        'raise RuntimeError("test-failure")',
        language="python",
        work_dir=str(tmp_path / "error"),
    )
    assert result.status == ExecutionStatus.ERROR
    assert "test-failure" in result.error
    docker_runtime[1].assert_called_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["python", "bash"])
@pytest.mark.parametrize("input_kind", ["missing", "symlink"])
async def test_live_docker_rejected_input_never_executes_locally(
    tmp_path, docker_runtime, capsys, language, input_kind
):
    """Real upload rejection must not turn container execution into host execution."""
    client, create, selected = docker_runtime
    input_path = tmp_path / "input.txt"
    if input_kind == "symlink":
        source = tmp_path / "source.txt"
        source.write_text("test input")
        input_path.symlink_to(source)
    work_dir = tmp_path / "workspace"
    marker = work_dir / "unexpected-execution.txt"
    code = (
        'from pathlib import Path; Path("unexpected-execution.txt").write_text("ran")'
        if language == "python"
        else "printf ran > unexpected-execution.txt"
    )

    with pytest.raises(RuntimeError):
        await _execution.run_code(
            code,
            language=language,
            work_dir=str(work_dir),
            input_paths=[str(input_path)],
        )

    # Confirm setup reached the input upload, not an unrelated Docker failure.
    output = capsys.readouterr().out
    assert str(input_path) in output
    if input_kind == "symlink":
        assert "Sandbox input must not be a symlink" in output
    assert not marker.exists()
    create.assert_called_once_with()
    assert all(not runtime.sessions for runtime in selected)
    # Failed sessions are never registered, so also check the daemon for leaks.
    for container in client.containers.list(
        all=True, filters={"name": "sandbox_agent_"}
    ):
        assert container.attrs["Config"]["WorkingDir"] != str(work_dir)
