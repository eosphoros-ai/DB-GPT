"""Session catalog regression: recovery, isolation, and deterministic expansion."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dbgpt.core.interface import report_capture
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    capture_python_execution,
    capture_sql_execution,
)
from dbgpt_app.openapi.api_v1.subagent import report_agent
from dbgpt_app.openapi.api_v1.subagent.result import SubagentArtifactSink
from dbgpt_app.openapi.api_v1.tools.evidence_catalog import (
    EvidenceCatalog,
    SessionArtifactSink,
)
from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
    _render_template_with_bindings,
    _resolve_template_references,
)
from dbgpt_app.openapi.api_v1.tools.report_evidence import (
    make_report_evidence_manifest,
)


def test_session_recovers_metrics_and_original_run(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    sink = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="session-A", run_id="turn-1"), catalog
    )
    sql_id = capture_sql_execution(
        sql="SELECT 42 AS gmv",
        database="test",
        duration_ms=1,
        columns=["gmv"],
        rows=[[42]],
        artifact_sink=sink,
    )
    python_id = capture_python_execution(
        code="REPORT_RESULT={'kpi': {'sales': 21}}",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"kpi": {"sales": 21, "category": "retail"}},
        artifact_sink=sink,
    )
    metrics = catalog.list_metrics("session-A")
    assert {metric["artifact_id"] for metric in metrics} == {sql_id, python_id}
    assert all(metric["run_id"] == "turn-1" for metric in metrics)
    assert all(metric["status"] == "selector_validated" for metric in metrics)

    restarted = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="session-A", run_id="turn-2"),
        catalog,
        include_prior=True,
    )
    recovered = restarted.snapshot()
    assert {artifact.artifact_id for artifact in recovered} == {sql_id, python_id}
    assert {artifact.execution.run_id for artifact in recovered} == {"turn-1"}
    fresh_turn = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="session-A", run_id="turn-3"), catalog
    )
    assert fresh_turn.snapshot() == []
    assert catalog.list_metrics("session-B") == []
    assert (
        SessionArtifactSink(
            ArtifactCaptureContext(conv_uid="session-B", run_id="turn-1"), catalog
        ).snapshot()
        == []
    )
    other_owner = EvidenceCatalog(tmp_path / "catalog.sqlite3", owner_id="someone-else")
    assert other_owner.list_metrics("session-A") == []
    assert other_owner.list_artifacts("session-A") == []

    metric = next(item for item in metrics if item["artifact_id"] == sql_id)
    resolved = _resolve_template_references(
        {"kpi": {"metric_id": metric["metric_id"]}},
        recovered,
        metric_map={item["metric_id"]: item for item in metrics},
    )
    assert resolved["kpi"]["raw"] == 42
    assert resolved["kpi"]["artifact_id"] == sql_id
    assert resolved["kpi"]["selector"] == metric["selector"]
    catalog.register(
        "session-A",
        next(a for a in recovered if a.artifact_id == sql_id),
        metric["selector"],
        label="商品 GMV",
        grain="全部订单",
        meaning_source="agent_declared",
    )
    annotated = next(
        item
        for item in catalog.list_metrics("session-A")
        if item["metric_id"] == metric["metric_id"]
    )
    assert annotated["label"] == "商品 GMV"
    assert annotated["grain"] == "全部订单"
    assert annotated["meaning_source"] == "agent_declared"
    same_run = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="session-A", run_id="turn-1"), catalog
    )
    same_run.record(next(a for a in sink.snapshot() if a.artifact_id == sql_id))
    assert (
        next(
            item
            for item in catalog.list_metrics("session-A")
            if item["metric_id"] == metric["metric_id"]
        )["label"]
        == "商品 GMV"
    )

    with pytest.raises(ValueError, match="EVIDENCE_SESSION_MISMATCH"):
        catalog.register("session-B", recovered[0], {"path": ["rows", 0, 0]})
    with pytest.raises(ValueError, match="EVIDENCE_METRIC_SCALAR_REQUIRED"):
        catalog.register("session-A", recovered[0], {"path": ["rows"]})
    python_artifact = next(a for a in recovered if a.artifact_id == python_id)
    with pytest.raises(ValueError, match="EVIDENCE_METRIC_SCALAR_REQUIRED"):
        catalog.register(
            "session-A",
            python_artifact,
            {"field": "kpi", "path": ["category"]},
        )


def test_metric_id_is_expanded_before_report_spec_validation(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    sink = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="spec-session", run_id="turn-1"), catalog
    )
    capture_sql_execution(
        sql="SELECT 42 AS gmv",
        database="test",
        duration_ms=1,
        columns=["gmv"],
        rows=[[42]],
        artifact_sink=sink,
    )
    metric = catalog.list_metrics("spec-session")[0]
    root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "skills/business-report/templates/business_report.html").is_file()
    )
    template = (
        root / "skills/business-report/templates/business_report.html"
    ).read_text(encoding="utf-8")
    html = _render_template_with_bindings(
        template,
        {
            "REPORT_SPEC": {
                "title": "测试报告",
                "kpis": [{"label": "GMV", "ref": {"metric_id": metric["metric_id"]}}],
                "sections": [
                    {
                        "heading": "分析",
                        "intro": [["GMV：", {"metric_id": metric["metric_id"]}]],
                    }
                ],
            }
        },
        sink.snapshot(),
        draft_state={"_report_artifact_sink": sink},
    )
    assert "42" in html
    assert metric["artifact_id"] in html
    with pytest.raises(ValueError, match="unknown metric_id"):
        _render_template_with_bindings(
            template,
            {
                "REPORT_SPEC": {
                    "kpis": [{"label": "GMV", "ref": {"metric_id": "metric-invented"}}]
                }
            },
            sink.snapshot(),
            draft_state={"_report_artifact_sink": sink},
        )


@pytest.mark.parametrize("row_objects", [False, True])
def test_truncated_sql_preview_cannot_register_shifted_row_coordinates(
    tmp_path, monkeypatch, row_objects
):
    from dbgpt_app.openapi.api_v1.tools import evidence_catalog

    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    sink = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="truncated-session", run_id="turn-1"), catalog
    )
    oversized = "X" * (report_capture.MAX_SQL_PREVIEW_BYTES + 1)
    rows = [{"value": oversized}, {"value": 42}] if row_objects else [[oversized], [42]]

    def forbidden_read(*args):
        raise AssertionError("automatic indexing must not reload a large result")

    with monkeypatch.context() as indexing_patch:
        indexing_patch.setattr(
            evidence_catalog, "select_artifact_result", forbidden_read
        )
        identifier = capture_sql_execution(
            sql="SELECT value FROM t",
            database="test",
            duration_ms=1,
            columns=["value"],
            rows=rows,
            artifact_sink=sink,
        )
    artifact = next(a for a in sink.snapshot() if a.artifact_id == identifier)
    assert artifact.result.inline["rows"] == rows[1:]
    assert artifact.result.inline["truncated"] is True
    assert catalog.list_metrics("truncated-session") == []
    column = "value" if row_objects else 0
    with pytest.raises(ValueError, match="EVIDENCE_METRIC_SCALAR_REQUIRED"):
        catalog.register("truncated-session", artifact, {"path": ["rows", 0, column]})
    assert catalog.list_metrics("truncated-session") == []
    metric = catalog.register(
        "truncated-session", artifact, {"path": ["rows", 1, column]}
    )
    restarted = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="truncated-session", run_id="turn-2"),
        catalog,
        include_prior=True,
    )
    restored = next(a for a in restarted.snapshot() if a.artifact_id == identifier)
    assert (
        catalog.register("truncated-session", restored, {"path": ["rows", 1, column]})[
            "metric_id"
        ]
        == metric["metric_id"]
    )
    bound = _resolve_template_references(
        {"kpi": {"metric_id": metric["metric_id"]}},
        restarted.snapshot(),
        metric_map={
            item["metric_id"]: item
            for item in catalog.list_metrics("truncated-session")
        },
    )
    assert bound["kpi"]["raw"] == 42
    assert bound["kpi"]["selector"] == {"path": ["rows", 1, column]}


def test_parallel_child_artifacts_keep_parent_session_and_child_attribution(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    parent = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="parent-session", run_id="turn-1"), catalog
    )

    def capture(index):
        child = SubagentArtifactSink(parent, f"child-{index}", f"Child {index}")
        return capture_sql_execution(
            sql=f"SELECT {index} AS metric",
            database="test",
            duration_ms=1,
            columns=["metric"],
            rows=[[index]],
            artifact_sink=child,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(capture, range(8)))
    artifacts = catalog.list_artifacts("parent-session")
    assert {artifact.artifact_id for artifact in artifacts} == set(ids)
    assert {artifact.execution.conv_uid for artifact in artifacts} == {"parent-session"}
    assert {artifact.execution.run_id for artifact in artifacts} == {"turn-1"}
    assert {artifact.metadata["agent_id"] for artifact in artifacts} == {
        f"child-{index}" for index in range(8)
    }
    assert len(catalog.list_metrics("parent-session")) == 8


def test_scalar_indexing_does_not_reread_full_result(tmp_path, monkeypatch):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    sink = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="fast-session", run_id="turn-1"), catalog
    )

    def forbidden_read(_artifact):
        raise AssertionError("indexing should use captured inline values")

    monkeypatch.setattr(report_capture, "read_artifact_result", forbidden_read)
    capture_sql_execution(
        sql="SELECT 1 AS a, 2 AS b",
        database="test",
        duration_ms=1,
        columns=["a", "b"],
        rows=[[1, 2]],
        artifact_sink=sink,
    )
    assert len(catalog.list_metrics("fast-session")) == 2


@pytest.mark.asyncio
async def test_report_manifest_exposes_only_visible_session_metrics(tmp_path):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    first = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="same-session", run_id="turn-1"), catalog
    )
    capture_sql_execution(
        sql="SELECT 1 AS first_value",
        database="test",
        duration_ms=1,
        columns=["first_value"],
        rows=[[1]],
        artifact_sink=first,
    )
    next_turn = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="same-session", run_id="turn-2"), catalog
    )
    capture_sql_execution(
        sql="SELECT 2 AS second_value",
        database="test",
        duration_ms=1,
        columns=["second_value"],
        rows=[[2]],
        artifact_sink=next_turn,
    )
    manifest = json.loads(
        await make_report_evidence_manifest({"_report_artifact_sink": next_turn})()
    )
    assert manifest["status"] == "ok"
    assert len(manifest["metrics"]) == 1
    assert manifest["metrics"][0]["run_id"] == "turn-2"
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["run_id"] == "turn-2"


@pytest.mark.asyncio
async def test_generate_report_records_declared_meaning_without_extra_model_call(
    tmp_path, monkeypatch
):
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    sink = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="meaning-session", run_id="turn-1"), catalog
    )
    artifact_id = capture_sql_execution(
        sql="SELECT 42 AS gmv",
        database="test",
        duration_ms=1,
        columns=["gmv"],
        rows=[[42]],
        artifact_sink=sink,
    )

    async def already_rendered(*_args, **_kwargs):
        return True

    monkeypatch.setattr(report_agent, "render_saved_report", already_rendered)
    monkeypatch.setattr(
        report_agent,
        "_completed_report_response",
        lambda _state: '{"status":"completed"}',
    )
    tool = report_agent.make_generate_report_tool(
        react_state={"conv_id": "meaning-session", "_report_artifact_sink": sink},
        skills_dir=str(tmp_path),
        llm_client=None,
    )
    response = await tool(
        instructions="test",
        metric_definitions=[
            {
                "artifact_id": artifact_id,
                "selector": {"path": ["rows", 0, 0]},
                "meaning": "商品 GMV",
                "grain": "全部订单",
            }
        ],
    )
    assert json.loads(response)["status"] == "completed"
    metric = catalog.list_metrics("meaning-session")[0]
    assert metric["label"] == "商品 GMV"
    assert metric["grain"] == "全部订单"
    assert metric["meaning_source"] == "agent_declared"


def test_multirun_checkpoint_and_prior_dependency(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    first = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="multirun", run_id="turn-1"), catalog
    )
    source = capture_python_execution(
        code="source",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"value": 42},
        artifact_sink=first,
    )
    second = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="multirun", run_id="turn-2"),
        catalog,
        include_prior=True,
    )
    state = {"conv_id": "multirun", "_report_artifact_sink": second}
    report_repair._save_checkpoint(state, {}, "retry")
    restored = report_repair.restore_report_checkpoint("multirun", {})
    assert {a.execution.run_id for a in restored.snapshot()} == {"turn-1"}
    capture_python_execution(
        code="derived",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"value": 84},
        input_artifact_ids=[source],
        artifact_sink=second,
    )
    for _ in range(2):
        report_repair._save_checkpoint(state, {}, "retry")
        restored = report_repair.restore_report_checkpoint("multirun", {})
        assert {a.execution.run_id for a in restored.snapshot()} == {"turn-1", "turn-2"}
        session_sink = SessionArtifactSink(
            restored.context, catalog, include_prior=True
        )
        for artifact in restored.snapshot():
            session_sink.restore_artifact(artifact)
        state["_report_artifact_sink"] = session_sink
    foreign = SessionArtifactSink(
        ArtifactCaptureContext(conv_uid="other", run_id="turn-1"), catalog
    )
    with pytest.raises(ValueError, match="belongs to conversation"):
        foreign.restore_artifact(restored.snapshot()[0])
    with pytest.raises(ValueError, match="belongs to run"):
        second.record(first.snapshot()[0])
