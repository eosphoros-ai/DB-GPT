"""Real local Python calls share files while keeping per-call capture separate."""

import inspect
import json

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    read_artifact_result,
)
from dbgpt_app.openapi.api_v1.tools.code_interpreter import make_code_interpreter


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    from dbgpt.configs import model_config
    from dbgpt_sandbox.sandbox.execution_layer import runtime_factory

    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "local")
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="file-continuity"))
    state = {"conv_id": "file-continuity", "_report_artifact_sink": sink}
    return state, sink


async def execute(state, code):
    return json.loads(await inspect.unwrap(make_code_interpreter(state))(code=code))


@pytest.mark.asyncio
async def test_relative_files_survive_calls_but_python_variables_do_not(workspace):
    state, sink = workspace
    await execute(
        state,
        "from pathlib import Path\nPath('result.txt').write_text('step-one')\n"
        "temporary_variable = 7\nREPORT_RESULT = {'first': True}",
    )
    response = await execute(
        state,
        "from pathlib import Path\n"
        "REPORT_RESULT = {'text': Path('result.txt').read_text(),\n"
        "'variables_persist': 'temporary_variable' in globals()}",
    )
    artifact = next(
        a for a in sink.snapshot() if a.artifact_id == response["artifact_id"]
    )
    assert artifact.status == "succeeded", artifact.error
    assert read_artifact_result(artifact) == {
        "text": "step-one",
        "variables_persist": False,
    }
    other = await execute(
        {"conv_id": "another-session"},
        "from pathlib import Path\nprint(Path('result.txt').exists())",
    )
    assert any(c.get("content") == "False" for c in other["chunks"])


@pytest.mark.asyncio
async def test_prior_result_and_images_are_not_recaptured(workspace):
    state, sink = workspace
    first = await execute(
        state,
        "from PIL import Image\n"
        "Image.new('RGB', (2,2), 'red').save('plot.png')\n"
        "REPORT_RESULT = {'first': 1}",
    )
    assert sum(c["output_type"] == "image" for c in first["chunks"]) == 1
    second = await execute(state, "print('second call, no new outputs')")
    artifact = next(
        a for a in sink.snapshot() if a.artifact_id == second["artifact_id"]
    )
    assert artifact.status == "succeeded", artifact.error
    assert artifact.result is None
    assert not any(c["output_type"] == "image" for c in second["chunks"])


@pytest.mark.asyncio
async def test_overwritten_image_is_captured_as_a_new_output(workspace):
    state, sink = workspace
    first = await execute(
        state, "from PIL import Image\nImage.new('RGB', (2,2), 'red').save('plot.png')"
    )
    second = await execute(
        state,
        "from PIL import Image\nImage.new('RGB', (2,2), 'blue').save('plot.png')",
    )
    first_images = [
        c["content"] for c in first["chunks"] if c["output_type"] == "image"
    ]
    second_images = [
        c["content"] for c in second["chunks"] if c["output_type"] == "image"
    ]
    assert len(first_images) == len(second_images) == 1
    assert first_images[0] != second_images[0]
