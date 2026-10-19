"""Real skill execution, snapshot persistence and authenticated download regressions."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt._private.config import Config
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.agent.skill import manage
from dbgpt.component import SystemApp
from dbgpt.configs import model_config
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    artifact_content_path,
    artifact_storage_root,
    capture_file_artifact,
    snapshot_execution_files,
)
from dbgpt.storage.metadata.db_manager import DatabaseManager
from dbgpt_app.openapi.api_v1.tools.code_interpreter import build_execution_env
from dbgpt_app.openapi.api_v1.tools.read_file import make_read_file
from dbgpt_app.openapi.api_v1.tools.skill_tools import make_execute_skill_script_file
from dbgpt_serve.report.api import endpoints
from dbgpt_serve.report.config import ServeConfig
from dbgpt_serve.report.models import models
from dbgpt_serve.report.models.dao import ReportDao
from dbgpt_serve.report.service import ReportService


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path / "pilot"))
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(tmp_path / "skills"))
    script_dir = tmp_path / "skills" / "safe-reader" / "scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "read.py").write_text(
        "import sys\nfrom pathlib import Path\nprint(Path(sys.argv[1]).read_text())\n",
        encoding="utf-8",
    )
    app = SystemApp()
    monkeypatch.setattr(Config(), "SYSTEM_APP", app)
    monkeypatch.setattr(manage, "_SYSTEM_APP", None)
    manage.initialize_skill(app)
    yield tmp_path
    endpoints._reset_endpoints()


def report_client(tmp_path, sink):
    manager = DatabaseManager()
    manager.init_db(
        "sqlite:///" + (tmp_path / "reports.sqlite").as_posix(),
        engine_args={"connect_args": {"check_same_thread": False}},
    )
    for value in vars(models).values():
        if isinstance(value, type) and getattr(value, "__table__", None) is not None:
            value.__table__.create(manager._engine, checkfirst=True)
    service = ReportService(dao=ReportDao(db_manager=manager))
    record = service.assemble_and_save(
        owner_id="owner",
        report_id="security-regression",
        title="Canary report",
        conv_uid=sink.context.conv_uid,
        final_content="Benign result",
        artifacts=sink.snapshot(),
    )
    app = FastAPI()
    endpoints.init_endpoints(
        SystemApp(app), service, ServeConfig(api_keys="regression-test-key")
    )
    app.include_router(endpoints.router, prefix="/api/v1/reports")
    return TestClient(app), record


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["args", "argv"])
@pytest.mark.parametrize("skill", ["safe-reader", "missing-skill"])
async def test_host_file_never_archived_or_downloadable(runtime, mode, skill):
    outside = runtime / "outside-session.txt"
    content = b"host-only benign canary\n"
    outside.write_bytes(content)
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="security-denied"))
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    assert "Access denied" in make_read_file(state)(str(outside))
    execute = make_execute_skill_script_file(state)
    pack = ToolPack([execute._tool])
    arguments = (
        {"argv": [str(outside)]}
        if mode == "argv"
        else {"args": {"nested": {"candidate": str(outside)}}}
    )
    result = json.loads(
        await pack.async_execute(
            resource_name="execute_skill_script_file",
            skill_name=skill,
            script_file_name="read.py",
            **arguments,
        )
    )
    assert result.get("success") is False
    assert "FILE_INPUT_NOT_AUTHORIZED" in json.dumps(result)
    assert not [
        a for a in sink.snapshot() if getattr(a, "reference_type", None) == "file"
    ]
    assert not (
        artifact_storage_root() / (hashlib.sha256(content).hexdigest() + ".txt")
    ).exists()
    client, record = report_client(runtime, sink)
    url = (
        f"/api/v1/reports/{record.report_id}/runs/{record.run_id}"
        "/artifacts/reference-denied/content"
    )
    with client:
        response = client.get(
            url + "?part=source",
            headers={"Authorization": "Bearer regression-test-key", "user-id": "owner"},
        )
        assert response.status_code == 404
        assert content not in response.content


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [True, False])
async def test_authorized_upload_runs_and_remains_owner_scoped(runtime, legacy):
    attachment = runtime / "attachment.txt"
    attachment.write_text("authorized attachment canary", encoding="utf-8")
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="security-allowed"))
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    if legacy:
        state["file_path"] = str(attachment)
    else:
        state.update(
            session_files=[{"file_id": "file-1", "status": "ready"}],
            session_file_paths={"file-1": str(attachment)},
        )
    execute = make_execute_skill_script_file(state)
    result = json.loads(
        await ToolPack([execute._tool]).async_execute(
            resource_name="execute_skill_script_file",
            skill_name="safe-reader",
            script_file_name="read.py",
            argv=[str(attachment)],
        )
    )
    assert result.get("success") is not False, result
    python = next(a for a in sink.snapshot() if a.artifact_id == result["artifact_id"])
    assert python.status == "succeeded"
    assert "authorized attachment canary" in python.stdout
    reference = next(
        a for a in sink.snapshot() if getattr(a, "reference_type", None) == "file"
    )
    assert artifact_content_path(reference.uri).read_bytes() == attachment.read_bytes()
    client, record = report_client(runtime, sink)
    url = (
        f"/api/v1/reports/{record.report_id}/runs/{record.run_id}"
        f"/artifacts/{reference.artifact_id}/content?part=source"
    )
    headers = {"Authorization": "Bearer regression-test-key", "user-id": "owner"}
    with client:
        assert client.get(url, headers=headers).content == attachment.read_bytes()
        assert client.get(url.split("?")[0], headers=headers).status_code == 404
        assert (
            client.get(url, headers={**headers, "user-id": "other"}).status_code == 404
        )
        assert client.get(url).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "deleted"])
async def test_unready_attachment_and_stale_legacy_path_are_denied(runtime, status):
    source = runtime / "stale.txt"
    source.write_text("must not archive")
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="unready"))
    state = {
        "conv_id": sink.context.conv_uid,
        "_report_artifact_sink": sink,
        "file_path": str(source),
        "session_files": [{"file_id": "stale", "status": status}],
        "session_file_paths": {"stale": str(source)},
    }
    execute = make_execute_skill_script_file(state)
    result = json.loads(
        await ToolPack([execute._tool]).async_execute(
            resource_name="execute_skill_script_file",
            skill_name="safe-reader",
            script_file_name="read.py",
            argv=[str(source)],
        )
    )
    assert result["success"] is False, result
    assert "FILE_INPUT_NOT_AUTHORIZED" in str(result)
    assert not sink.snapshot()


def test_code_environment_reads_selected_authorized_snapshots(runtime):
    first, second = runtime / "first.txt", runtime / "second.txt"
    first.write_text("selected canary")
    second.write_text("unselected canary")
    manifest = runtime / "files.json"
    manifest.write_text(json.dumps({"first": str(first), "second": str(second)}))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="code-inputs"))
    env = build_execution_env(
        work_dir=str(runtime),
        file_path=str(first),
        files_json_path=str(manifest),
        selected_file_ids=["first"],
        artifact_sink=sink,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,json;from pathlib import Path;"
                "m=json.loads(Path(os.environ['FILES_JSON']).read_text());"
                "assert list(m)==['first'];"
                "assert Path(m['first']).read_text()=='selected canary';"
                "assert Path(os.environ['FILE_PATH']).read_text()=='selected canary';"
                "print('selected snapshots read successfully')"
            ),
        ],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    assert "selected snapshots read successfully" in result.stdout
    refs = sink.snapshot()
    assert all(a.locator.get("path") != str(second.resolve()) for a in refs)
    assert len(json.loads(env["DBGPT_INPUT_ARTIFACT_IDS"])) == 2


def test_symlink_cannot_upgrade_authorized_filename(runtime):
    outside = runtime / "outside"
    outside.mkdir()
    host = outside / "host.txt"
    host.write_text("host canary")
    alias = runtime / "attachment-directory"
    if os.name == "nt":
        # Directory junctions exercise the same real-path escape without
        # requiring Windows' optional symbolic-link privilege.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(outside)],
            check=True,
            capture_output=True,
        )
    else:
        alias.symlink_to(outside, target_is_directory=True)
    link = alias / "host.txt"
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="symlink"))
    with pytest.raises(ValueError, match="FILE_INPUT_NOT_AUTHORIZED"):
        snapshot_execution_files(
            {"input": str(link)}, sink, action="test", allowed_paths=[link]
        )
    assert not sink.snapshot()


def test_only_unchanged_same_session_artifact_can_be_reused(runtime):
    source = runtime / "output.txt"
    source.write_text("verified output canary")
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="artifact-owner"))
    artifact = capture_file_artifact(source, sink, action="trusted-output")
    rewritten, ids = snapshot_execution_files(
        {"input": str(source)}, sink, action="reuse"
    )
    assert ids and Path(rewritten["input"]).read_bytes() == source.read_bytes()
    foreign = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="other-session"))
    with pytest.raises(ValueError, match="FILE_INPUT_NOT_AUTHORIZED"):
        snapshot_execution_files(
            {"input": str(artifact_content_path(artifact.uri))}, foreign, action="reuse"
        )
    source.write_text("changed output is not the verified snapshot")
    with pytest.raises(ValueError, match="FILE_INPUT_NOT_AUTHORIZED"):
        snapshot_execution_files({"input": str(source)}, sink, action="reuse")
