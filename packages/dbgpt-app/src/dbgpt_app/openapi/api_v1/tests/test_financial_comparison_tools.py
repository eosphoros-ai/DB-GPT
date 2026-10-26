import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    _artifact,
    has_comparison_intent,
    make_financial_tools,
)
from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.tests.conftest import (
    isolated_service as isolated_service,
)
from dbgpt_serve.financial_analysis.tests.test_comparison_recovery import (
    RecordingAnalyzer,
)
from dbgpt_serve.session_file.api.endpoints import SessionFileApiError


def test_attachment_count_alone_does_not_imply_comparison():
    assert not has_comparison_intent("阅读附件中的两份文件")
    assert not has_comparison_intent("不要对比，请单独分析")
    assert has_comparison_intent("请横向比较这几份年报")
    assert has_comparison_intent("Compare annual reports")


@pytest.mark.asyncio
async def test_comparison_without_model_name_uses_serial_topic_path(
    isolated_service, monkeypatch
):
    service, _, _, _ = isolated_service
    from dbgpt_serve.financial_analysis import parallel

    def forbidden(*args, **kwargs):
        raise AssertionError("TopicGenerator must not receive model=None")

    monkeypatch.setattr(parallel, "TopicGenerator", forbidden)
    state = {
        "owner_id": "alice",
        "conv_id": "scope",
        "financial_user_query": "比较财报",
        "financial_llm_client": object(),
        "model_name": None,
        "session_files": [
            SimpleNamespace(file_id="a", name="a.pdf"),
            SimpleNamespace(file_id="b", name="b.pdf"),
        ],
    }
    prepare = next(
        fn
        for fn in make_financial_tools(state, service=service)
        if fn.__name__ == "prepare_financial_comparison"
    )
    result = json.loads(await prepare(file_ids=["a", "b"], comparison_kind="peer"))
    assert result["model_context"]["next_action"]["tool"] == "save_financial_topic"
    assert (
        state["financial_report_context"]["workflow"]["topics"][0]["status"]
        == "running"
    )


@pytest.mark.asyncio
async def test_comparison_tool_rejects_missing_intent_before_accessing_service():
    state = {
        "owner_id": "alice",
        "conv_id": "scope",
        "financial_user_query": "阅读附件",
        "session_files": [
            SimpleNamespace(file_id="a", name="a.pdf"),
            SimpleNamespace(file_id="b", name="b.pdf"),
        ],
    }
    tools = make_financial_tools(state, service=SimpleNamespace())
    prepare = next(t for t in tools if t.__name__ == "prepare_financial_comparison")
    with pytest.raises(ValueError, match="未明确要求"):
        await prepare(file_ids=["a", "b"], comparison_kind="peer")


@pytest.mark.asyncio
async def test_migration_required_does_not_announce_extraction():
    state = {
        "owner_id": "alice",
        "conv_id": "scope",
        "financial_user_query": "请比较这两份财报",
        "session_files": [
            SimpleNamespace(file_id="a", name="a.pdf"),
            SimpleNamespace(file_id="b", name="b.pdf"),
        ],
    }
    create = Mock(
        side_effect=SessionFileApiError(
            503, "COMPARISON_MIGRATION_REQUIRED", "财报对比需要先显式迁移数据库。"
        )
    )
    callback = AsyncMock()
    tools = make_financial_tools(
        state,
        service=SimpleNamespace(comparisons=SimpleNamespace(create=create)),
        stream_callback=callback,
    )
    prepare = next(t for t in tools if t.__name__ == "prepare_financial_comparison")
    with pytest.raises(SessionFileApiError) as error:
        await prepare(file_ids=["a", "b"], comparison_kind="peer")
    assert error.value.err_code == "COMPARISON_MIGRATION_REQUIRED"
    create.assert_called_once()
    callback.assert_not_awaited()


def test_comparison_artifact_has_explicit_mode_and_no_single_company_identity():
    report = {
        "mode": "comparison",
        "revision": "saved",
        "comparison": {"title": "甲与乙横向对比"},
        "report": {"run": {"id": "12345678-1234-4234-8234-123456789012"}},
        "workflow": {"status": "published"},
    }
    artifact = _artifact(report, "scope")["content"]
    assert artifact["title"] == report["comparison"]["title"]
    assert artifact["mode"] == "comparison" and artifact["published"] is True
    assert "companyName" not in json.dumps(artifact)


@pytest.mark.asyncio
async def test_chat_comparison_prepare_topics_review_and_pinned_read(isolated_service):
    service, _, calls, _ = isolated_service
    state = {
        "owner_id": "alice",
        "conv_id": "scope",
        "model_name": "synthetic",
        "financial_user_query": "请横向对比这两家公司年度报告。",
        "session_files": [
            SimpleNamespace(file_id=i, name=i + ".pdf") for i in ["a", "b"]
        ],
    }
    tools = {
        tool.__name__: tool for tool in make_financial_tools(state, service=service)
    }
    await tools["prepare_financial_comparison"](["a", "b"], "peer")
    run_id = state["financial_report_context"]["report"]["run"]["id"]
    adapter = RecordingAnalyzer()
    for topic_id in workflow.TOPICS:
        await tools["get_financial_topic"](run_id, topic_id)
        report = service.get("alice", "scope", run_id, report=True)
        findings = json.loads(
            adapter(dict(report, _activeTopic=topic_id), "alice", "scope")
        )["findings"]
        await tools["save_financial_topic"](
            run_id=run_id,
            revision=report["revision"],
            topic_id=topic_id,
            findings=findings,
        )
    report = service.get("alice", "scope", run_id, report=True)
    await tools["review_financial_report"](
        run_id, report["revision"], adapter.review(report, "alice", "scope")
    )
    published = state["financial_report_context"]
    assert published["workflow"]["status"] == "published"
    assert calls == ["a", "b"]
    reply = json.loads(
        await tools["read_financial_report"](run_id, revision=published["revision"])
    )
    assert (
        reply and state["financial_report_context"]["revision"] == published["revision"]
    )
