import json
import time
from copy import deepcopy

import pytest

from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.service import FinancialAnalysisService

from .conftest import wait_ready
from .test_comparison_analysis import comparison_finding
from .test_comparison_service import create


class RecordingAnalyzer:
    """Deterministic SYNTHETIC model adapter; not a real semantic acceptance."""

    model = "synthetic-recovery-adapter"

    def __init__(self):
        self.calls = []

    def __call__(self, report, owner, session_id):
        topic_id = report["_activeTopic"]
        self.calls.append(topic_id)
        _, section, codes, _ = workflow.TOPICS[topic_id]
        entity = report["comparison"]["entities"][0]["id"]
        facts = [
            f
            for f in report["facts"]
            if f["entityId"] == entity
            and f["metricCode"] in codes
            and f.get("normalizedValue") is not None
        ]
        return json.dumps(
            {
                "findings": [
                    {
                        "section": section,
                        "title": "合成披露与解释限制",
                        "summary": "；".join("{{fact:" + f["id"] + "}}" for f in facts)
                        + "，需进一步核对附注。",
                        "supportStatus": "partial",
                        "factIds": [f["id"] for f in facts],
                        "calculationIds": [],
                        "evidenceExcerptIds": [],
                        "counterEvidence": [],
                        "unresolvedQuestions": ["仍待核对附注。"],
                        "entityIds": [entity],
                        "periods": sorted({f["fiscalPeriod"] for f in facts}),
                        "metricCodes": sorted({f["metricCode"] for f in facts}),
                        "subjectEntityId": entity,
                        "baselineEntityId": None,
                        "comparisonDirection": "none",
                    }
                ]
            },
            ensure_ascii=False,
        )

    def review(self, report, owner, session_id):
        return [
            {
                "topic_id": t["id"],
                "verdict": "pass"
                if t["status"] in {"ready", "reviewed"}
                else "insufficient",
                "directionChecked": True,
                "scopeChecked": True,
                "causalityChecked": True,
                "note": "合成适配器核对，仅用于流程测试，不是人工或模型验收。",
            }
            for t in report["workflow"]["topics"]
        ]


def wait_analysis(service, run_id):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        state = service.get("alice", "scope", run_id)
        if (
            state["status"] not in {"pending", "running"}
            and state["stage"] != "agent_topics"
        ):
            return service.get("alice", "scope", run_id, report=True)
        time.sleep(0.01)
    raise AssertionError("Synthetic topic retry did not finish")


def test_restart_and_explicit_resume_preserve_saved_topic_and_documents(
    isolated_service,
):
    service, _, calls, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    report = service.update_agent_workflow(
        "alice", "scope", run_id, report["revision"], "start", topic_id="operating"
    )
    report = service.update_agent_workflow(
        "alice",
        "scope",
        run_id,
        report["revision"],
        "save",
        topic_id="operating",
        findings=[comparison_finding(report)],
    )
    saved = deepcopy(report["findings"])
    # save advances to the next topic. Emulate a process exiting before it saves.
    restarted = FinancialAnalysisService(service.registry, extractor=service.extractor)
    try:
        interrupted = restarted.get("alice", "scope", run_id, report=True)
        assert interrupted["lifecycle"]["stage"] == "interrupted"
        assert interrupted["findings"] == saved
        assert calls == ["a", "b"]
        restarted.comparisons.resume("alice", "scope", run_id, interrupted["revision"])
        wait_ready(restarted, run_id)
        resumed = restarted.get("alice", "scope", run_id, report=True)
        assert resumed["findings"] == saved and calls == ["a", "b"]
        assert workflow.topic(resumed, "operating")["status"] == "ready"
    finally:
        restarted.close()


def test_standalone_retry_runs_one_topic_and_keeps_old_publication(isolated_service):
    service, _, extraction_calls, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    analyzer = RecordingAnalyzer()
    service.analyzer = analyzer
    report = service.get("alice", "scope", run_id, report=True)
    report["analysis"]["driver"] = "standalone"
    service._update(run_id, report_json=json.dumps(report))
    published = service.comparisons.analyze("alice", "scope", run_id, report)
    assert published["workflow"]["status"] == "published"
    assert len(analyzer.calls) == 6
    preserved = {
        topic["id"]: deepcopy(topic["findingIds"])
        for topic in published["workflow"]["topics"]
        if topic["id"] != "expenses"
    }
    service.comparisons.retry_topic(
        "alice", "scope", run_id, published["revision"], "expenses"
    )
    revised = wait_analysis(service, run_id)
    assert revised["workflow"]["status"] == "published"
    assert analyzer.calls[6:] == ["expenses"]
    assert extraction_calls == ["a", "b"]
    assert {
        topic["id"]: topic["findingIds"]
        for topic in revised["workflow"]["topics"]
        if topic["id"] != "expenses"
    } == preserved
    assert service.get(
        "alice", "scope", run_id, report=True, revision=published["revision"]
    ) == workflow.public_snapshot(published)


@pytest.mark.asyncio
async def test_chat_comparison_prepare_topics_review_and_pinned_read(isolated_service):
    from types import SimpleNamespace

    from dbgpt_app.openapi.api_v1.tools.financial_tools import make_financial_tools

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


def test_invalid_model_review_is_bounded_and_leaves_explicit_draft(isolated_service):
    service, _, calls, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    adapter = RecordingAnalyzer()
    review_calls = []

    def invalid_review(report, owner, session_id):
        review_calls.append(report.get("_reviewIssues"))
        return [{"topic_id": "unknown"}]

    adapter.review = invalid_review
    service.analyzer = adapter
    report = service.get("alice", "scope", run_id, report=True)
    report["analysis"]["driver"] = "standalone"
    service._update(run_id, report_json=json.dumps(report))
    result = service.comparisons.analyze("alice", "scope", run_id, report)
    assert len(review_calls) == 2 and review_calls[1]
    assert result["workflow"]["status"] == "draft"
    assert result["lifecycle"]["stage"] == "awaiting_revision"
    assert result["findings"] and calls == ["a", "b"]
    assert len(result["analysis"]["reviewIssues"]) == 2


def test_restart_during_extraction_retries_only_interrupted_document(isolated_service):
    from dbgpt_serve.financial_analysis.models import (
        FinancialRunDocumentEntity as Member,
    )
    from dbgpt_serve.financial_analysis.models import FinancialRunEntity as Run

    service, _, calls, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    with service.session() as session:
        row = session.query(Run).filter_by(id=run_id).one()
        row.status, row.stage = "running", "extract"
        member = session.query(Member).filter_by(run_id=run_id, file_id="b").one()
        member.status, member.extracted_json = "running", None
    restarted = FinancialAnalysisService(service.registry, extractor=service.extractor)
    try:
        state = restarted.get("alice", "scope", run_id)
        assert state["status"] == "failed"
        assert [m["status"] for m in state["members"]] == ["completed", "interrupted"]
        report = restarted.get("alice", "scope", run_id, report=True)
        restarted.comparisons.resume("alice", "scope", run_id, report["revision"])
        wait_ready(restarted, run_id)
        assert calls.count("a") == 1 and calls.count("b") == 2
    finally:
        restarted.close()
