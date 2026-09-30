"""Agent-owned analysis: actual storage and calculations, no nested model call."""

import json
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    finalize_financial_answer,
    financial_completion_error,
    make_financial_tools as _make_financial_tools,
    publication_example,
)

from .test_analysis import draft
from .test_runs import extraction, upload


def make_financial_tools(*args, **kwargs):
    """Keep regression coverage for existing single-publication reports."""
    return _make_financial_tools(*args, sectional=False, **kwargs)


def payload(value):
    return json.loads(json.loads(value)["chunks"][-1]["content"])


@pytest.mark.asyncio
async def test_agent_prepares_publishes_and_reopens_with_scoped_artifact(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = extraction

    def unexpected_model(*args):
        pytest.fail("The agent must supply conclusions without a nested analyzer")

    backend.analyzer = unexpected_model
    file_id = upload(client)
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "model_name": "agent-model",
        "session_files": [SimpleNamespace(file_id=file_id, name="年报.pdf")],
    }
    prepare, publish, read = make_financial_tools(state, service=backend)
    assert await financial_completion_error(state, service=backend) is None
    result = await prepare()
    prepared = payload(result)
    example = publication_example(state["financial_report_context"])
    assert prepared["publication_example"] == example
    assert prepared["data"]["calculations"][0]["reference"].startswith("{{calculation:")
    run_id, revision = prepared["run_id"], prepared["revision"]
    assert "publish_financial_report" in await financial_completion_error(
        state, service=backend
    )
    artifact = json.loads(result)["chunks"][0]["content"]
    assert artifact["kind"] == "financial-report"
    assert artifact["sessionId"] == "s1" and artifact["runId"] == run_id
    assert "file_path" not in artifact
    report = backend.get("alice", "s1", run_id, report=True)
    assert report["analysis"]["driver"] == "agent"
    assert report["analysis"]["status"] == "partial"
    assert report["analysis"]["modelName"] == "agent-model"
    assert payload(await prepare())["run_id"] == run_id

    invalid = dict(draft(report), summary="收入为999亿元")
    rejected = await publish(run_id, revision, [invalid])
    rejection = json.loads(rejected)
    assert "自动修正" in rejection["chunks"][0]["content"]
    assert "Unreferenced number" not in rejection["chunks"][0]["content"]
    assert rejection["repair"]["issues"][0]["field"] == "summary"
    assert rejection["repair"]["example"] == example
    assert backend.get("alice", "s1", run_id, report=True) == report
    final = payload(await publish(run_id, revision, [draft(report)]))
    assert final["analysis"]["status"] == "partial"
    assert len(final["findings"]) == 1
    assert final["revision"] != revision
    summary = finalize_financial_answer("完整分析已完成，收入999亿元", state)
    assert "部分分析" in summary and "999" not in summary
    assert await financial_completion_error(state, service=backend) is None
    next_turn = {"owner_id": "alice", "conv_id": "s1"}
    assert "read_financial_report" in await financial_completion_error(
        next_turn, service=backend
    )
    _, _, read_next = make_financial_tools(next_turn, service=backend)
    await read_next()
    assert await financial_completion_error(next_turn, service=backend) is None
    assert payload(await read())["run_id"] == run_id
    assert payload(await read(run_id))["findings"] == final["findings"]
    assert "publication_instructions" not in payload(await read())
    fact = next(f for f in report["facts"] if f["metricCode"] == "revenue")
    answer = finalize_financial_answer("本期情况：{{fact:" + fact["id"] + "}}。", state)
    assert fact["displayValue"] in answer and "{{" not in answer
    assert "物理第 1 页" in answer
    degraded = finalize_financial_answer(
        "收入999亿元，{{fact:" + fact["id"] + "}}", state
    )
    assert "999" not in degraded and "解释未通过校验" in degraded
    assert "回答未通过" in finalize_financial_answer("{{fact:foreign}}", state)
    assert backend.get("alice", "s1", run_id, report=True)["facts"] == report["facts"]
    with pytest.raises(Exception, match="报告已更新"):
        await publish(run_id, revision, [draft(report)])

    for owner, session in [("bob", "s1"), ("alice", "other")]:
        assert (
            await financial_completion_error(
                {"owner_id": owner, "conv_id": session}, service=backend
            )
            is None
        )
        _, foreign_publish, foreign_read = make_financial_tools(
            {"owner_id": owner, "conv_id": session}, service=backend
        )
        with pytest.raises(Exception):
            await foreign_read(run_id)
        with pytest.raises(Exception):
            await foreign_read()
        with pytest.raises(Exception):
            await foreign_publish(run_id, revision, [])


@pytest.mark.asyncio
async def test_agent_requires_unambiguous_current_attachment(stack):
    _, serve = stack
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [
            SimpleNamespace(file_id="a", name="a.pdf"),
            SimpleNamespace(file_id="b", name="b.pdf"),
        ],
    }
    prepare, _, _ = make_financial_tools(state, service=serve.financial_analysis)
    for file_id in ["", "foreign"]:
        with pytest.raises(ValueError, match="请选择"):
            await prepare(file_id)


@pytest.mark.asyncio
async def test_repeated_invalid_findings_end_with_explicit_data_only_report(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = extraction
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="年报.pdf")],
    }
    prepare, publish, _ = make_financial_tools(state, service=backend)
    prepared = payload(await prepare())
    run_id, revision = prepared["run_id"], prepared["revision"]
    report = state["financial_report_context"]
    invalid = dict(draft(report), summary="收入999亿元")
    for attempt in (1, 2):
        result = json.loads(await publish(run_id, revision, [invalid]))
        assert result["repair"]["attempt"] == attempt
        assert run_id in state["financial_pending"]
        assert backend.get("alice", "s1", run_id, report=True) == report
    final = payload(await publish(run_id, revision, [invalid]))
    assert final["analysis"]["status"] == "partial"
    assert final["analysis"]["rejectedCount"] == 1
    assert "仅保留财务数据" in final["analysis"]["error"]
    assert final["findings"] == []
    assert run_id not in state["financial_pending"]
    assert state["financial_report_context"]["facts"] == report["facts"]
    assert "999" not in finalize_financial_answer("分析完成", state)


@pytest.mark.asyncio
async def test_legacy_example_is_registered_for_persistent_sources(
    stack, tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import agentic_data_api

    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = extraction
    file_id = upload(client)
    stream, _ = backend.registry.open_download(
        owner_id="alice", session_id="s1", file_id=file_id
    )
    path = tmp_path / "python_uploads" / "alice" / "示例.pdf"
    path.parent.mkdir(parents=True)
    try:
        path.write_bytes(stream.read())
    finally:
        stream.close()
    monkeypatch.setattr(
        agentic_data_api, "_legacy_upload_base_dir", lambda: str(tmp_path)
    )
    state = {"owner_id": "alice", "conv_id": "s1", "file_path": str(path)}
    prepare, publish, _ = make_financial_tools(state, service=backend)
    prepared = payload(await prepare())
    # Original legacy path no longer needed to view sources or continue the report.
    path.unlink()
    result = payload(await publish(prepared["run_id"], prepared["revision"], []))
    assert result["analysis"]["status"] == "partial" and not result["findings"]
    report = backend.get("alice", "s1", prepared["run_id"], report=True)
    assert report["documents"][0]["fileId"] != file_id
    source, _, _ = backend.open_source(
        "alice", "s1", prepared["run_id"], report["documents"][0]["id"]
    )
    try:
        assert source.read().startswith(b"%PDF")
    finally:
        source.close()
