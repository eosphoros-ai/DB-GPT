import json
from uuid import uuid4

import pytest

from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.migrate import migrate
from dbgpt_serve.financial_analysis.service import FinancialAnalysisService
from dbgpt_serve.financial_analysis.workflow import TOPICS, topic_context
from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .conftest import wait_ready


@pytest.mark.parametrize("isolated_service", ["modern", "legacy"], indirect=True)
def test_restart_preserves_pinned_draft_before_updating_recovery_state(
    isolated_service,
):
    service, _, _, engine = isolated_service
    run_id = str(uuid4())
    service.create(
        "alice", "scope", "a", run_id, agent_model="synthetic", sectional=True
    )
    assert wait_ready(service, run_id)["status"] == "completed"
    before = service.get("alice", "scope", run_id, report=True)
    workflow.changed(before)
    service._update(
        run_id, stage="agent_topics", report_json=json.dumps(before, ensure_ascii=False)
    )
    service.close()
    restarted = FinancialAnalysisService(service.registry)
    try:
        migrate(engine, apply=True)
        restarted.refresh_schema()
        assert restarted.get(
            "alice", "scope", run_id, report=True, revision=before["revision"]
        ) == workflow.public_snapshot(before)
        current = restarted.get("alice", "scope", run_id, report=True)
        assert current["revision"] != before["revision"]
        assert current["facts"] == before["facts"]
    finally:
        restarted.close()


@pytest.mark.parametrize("isolated_service", ["modern", "legacy"], indirect=True)
def test_single_creation_topics_publication_question_source_and_old_export(
    isolated_service,
):
    service, _, calls, _ = isolated_service
    run_id = str(uuid4())
    service.create(
        "alice", "scope", "a", run_id, agent_model="synthetic", sectional=True
    )
    assert wait_ready(service, run_id)["status"] == "completed"
    initial = service.get("alice", "scope", run_id, report=True)
    report = initial
    assert report["schemaVersion"] == 1 and report["mode"] == "report"
    for topic_id in TOPICS:
        report = service.update_agent_workflow(
            "alice", "scope", run_id, report["revision"], "start", topic_id=topic_id
        )
        scoped = topic_context(report, topic_id)
        if scoped["missingRequiredMetrics"]:
            kwargs = {"findings": [], "missing_reason": "当前提取范围缺少必要科目。"}
        else:
            facts = scoped["data"]["facts"]
            kwargs = {
                "findings": [
                    {
                        "section": scoped["section"],
                        "title": "披露事实与解释限制",
                        "summary": "已披露："
                        + "；".join("{{fact:" + f["id"] + "}}" for f in facts)
                        + "，需结合附注核对。",
                        "supportStatus": "partial",
                        "factIds": [f["id"] for f in facts],
                        "calculationIds": [],
                        "evidenceExcerptIds": [],
                        "counterEvidence": [],
                        "unresolvedQuestions": ["变化原因需核对附注。"],
                    }
                ]
            }
        report = service.update_agent_workflow(
            "alice",
            "scope",
            run_id,
            report["revision"],
            "save",
            topic_id=topic_id,
            **kwargs,
        )
    reviews = [
        {
            "topic_id": t["id"],
            "verdict": "pass" if t["status"] == "ready" else "insufficient",
            "directionChecked": True,
            "scopeChecked": True,
            "causalityChecked": True,
            "note": "合成回归已核对引用与解释边界。",
        }
        for t in report["workflow"]["topics"]
    ]
    report = service.update_agent_workflow(
        "alice", "scope", run_id, report["revision"], "review", reviews=reviews
    )
    assert report["workflow"]["status"] == "published"
    assert calls == ["a"]
    if service.comparison_schema_ready:
        assert (
            service.get(
                "alice", "scope", run_id, report=True, revision=initial["revision"]
            )
            == initial
        )
    else:
        with pytest.raises(SessionFileApiError) as error:
            service.get(
                "alice", "scope", run_id, report=True, revision=initial["revision"]
            )
        assert error.value.err_code == "REVISION_NOT_FOUND"
        assert service.list_revisions("alice", "scope", run_id) == []
        initial = report
    assert (
        service.latest_agent_report("alice", "scope")["revision"] == report["revision"]
    )
    source, _, _ = service.open_source(
        "alice", "scope", run_id, report["documents"][0]["id"]
    )
    source.close()

    def answerer(snapshot, question, owner, session_id):
        return json.dumps(
            {
                "answer": "{{fact:"
                + snapshot["facts"][0]["id"]
                + "}}，具体原因仍需核对。",
                "factIds": [snapshot["facts"][0]["id"]],
                "calculationIds": [],
                "evidenceExcerptIds": [],
                "insufficientEvidence": False,
            }
        )

    answerer.model = "synthetic"
    service.answerer = answerer
    answer = service.ask("alice", "scope", run_id, initial["revision"], "营业收入")
    assert answer["revision"] == initial["revision"] and answer["citations"]
    exported = service.create_export(
        "alice", "scope", run_id, initial["revision"], "json"
    )
    content, _ = service.download_export("alice", "scope", run_id, exported["id"])
    assert json.loads(content)["revision"] == initial["revision"]
    assert calls == ["a"]
