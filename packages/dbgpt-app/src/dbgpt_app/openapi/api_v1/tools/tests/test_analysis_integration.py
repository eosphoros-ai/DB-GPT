"""Real CSV analysis through the public tool and local Python runtime."""

import json
from pathlib import Path

import pytest

from dbgpt.configs import model_config
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
)
from dbgpt_app.openapi.api_v1.tools.execute_analysis import make_execute_analysis
from dbgpt_sandbox.sandbox.execution_layer import runtime_factory
from dbgpt_serve.session_file.domain import SessionFileManifest, SessionFileStatus


@pytest.fixture
def analysis_files(tmp_path, monkeypatch):
    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path / "pilot"))
    # Select the real local executor; neither the runtime nor runner is replaced.
    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "local")
    mapping = {}
    manifests = []
    for ordinal, (file_id, values) in enumerate(
        [("alpha", [2, 3]), ("beta", [7]), ("gamma", [11, 13, 17])]
    ):
        path = tmp_path / f"{file_id}.csv"
        path.write_text("sales\n" + "\n".join(map(str, values)) + "\n")
        mapping[file_id] = str(path)
        manifests.append(
            SessionFileManifest(
                file_id=file_id,
                name=path.name,
                kind="table",
                media_type="text/csv",
                size=path.stat().st_size,
                status=SessionFileStatus.READY,
                ordinal=ordinal,
            )
        )
    manifest_path = tmp_path / "files.json"
    manifest_path.write_text(json.dumps(mapping))
    return {
        "conv_id": "actual-analysis",
        "file_path": mapping["alpha"],
        "files_json_path": str(manifest_path),
        "session_file_paths": mapping,
        "session_files": manifests,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("capture", [False, True])
@pytest.mark.parametrize("mode", ["legacy", "all", "subset"])
async def test_real_analysis_results_and_selected_inputs(analysis_files, mode, capture):
    state = dict(analysis_files)
    if mode == "legacy":
        for key in ("session_files", "files_json_path", "session_file_paths"):
            state.pop(key)
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid=state["conv_id"]))
    if capture:
        state["_report_artifact_sink"] = sink
    tool = make_execute_analysis(state)
    # Exclude the legacy primary attachment to exercise the actual subset path.
    response = json.loads(
        await tool(file_ids=["gamma", "beta"]) if mode == "subset" else await tool()
    )
    summaries = [c["content"] for c in response["chunks"] if c["output_type"] == "json"]
    expected = {
        "legacy": [(None, [2, 3])],
        "all": [("alpha", [2, 3]), ("beta", [7]), ("gamma", [11, 13, 17])],
        "subset": [("gamma", [11, 13, 17]), ("beta", [7])],
    }[mode]
    assert len(summaries) == len(expected), response
    for summary, (file_id, values) in zip(summaries, expected):
        assert summary.get("file_id") == file_id
        assert summary["shape"] == [len(values), 1]
        assert summary["columns"] == ["sales"]
        assert summary["head"] == [{"sales": value} for value in values]
    serialized = json.dumps(response)
    assert all(
        path not in serialized for path in analysis_files["session_file_paths"].values()
    )
    assert analysis_files["files_json_path"] not in serialized
    assert not list((Path(model_config.PILOT_PATH) / "tmp").rglob("_analysis_*.py"))
    if capture:
        python = next(a for a in sink.snapshot() if a.type == "python")
        assert python.status == "succeeded"
        assert python.input_artifact_ids
        references = [
            a for a in sink.snapshot() if getattr(a, "reference_type", None) == "file"
        ]
        if mode == "subset":
            assert all(a.locator.get("path") != state["file_path"] for a in references)
    else:
        assert not sink.snapshot()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conv_id",
    [
        "../../escape",
        "sub/dir",
        "back\\slash",
        "nul\x00byte",
        ".",
        "..",
        ".hidden",
        "CON",
        "x" * 300,
        "中文会话",
    ],
)
async def test_public_analysis_rejects_unsafe_id_before_writing(
    analysis_files, conv_id
):
    state = {**analysis_files, "conv_id": conv_id}
    source = Path(state["file_path"])
    original = source.read_bytes()
    result = json.loads(await make_execute_analysis(state)())
    assert any(
        "invalid conversation id" in str(c["content"]) for c in result["chunks"]
    ), result
    assert not Path(model_config.PILOT_PATH).exists()
    assert source.read_bytes() == original
    assert not (source.parent / "escape").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("conv_id", ["conv-test", "CON1", "a.b_c~d=e-1"])
async def test_real_analysis_accepts_safe_conversation_ids(analysis_files, conv_id):
    state = {"conv_id": conv_id, "file_path": analysis_files["file_path"]}
    result = json.loads(await make_execute_analysis(state)())
    summaries = [c["content"] for c in result["chunks"] if c["output_type"] == "json"]
    assert len(summaries) == 1, result
    assert summaries[0]["head"] == [{"sales": 2}, {"sales": 3}]
    directory = Path(model_config.PILOT_PATH) / "tmp" / conv_id
    assert directory.is_dir()
    assert directory.resolve().is_relative_to(
        (Path(model_config.PILOT_PATH) / "tmp").resolve()
    )
    assert not list(directory.glob("_analysis_*.py"))
