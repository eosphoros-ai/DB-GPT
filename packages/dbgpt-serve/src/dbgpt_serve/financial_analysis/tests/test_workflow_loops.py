import json
from copy import deepcopy

import pytest

from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .test_comparison_analysis import comparison_finding, comparison_report
from .workflow_fixtures import RecordingAnalyzer


def topic_findings(report, topic_id):
    scoped = dict(report, _activeTopic=topic_id)
    return json.loads(RecordingAnalyzer()(scoped, "alice", "scope"))["findings"]


def ready_report():
    report = comparison_report()
    for topic_id in workflow.TOPICS:
        report = workflow.start_topic(report, topic_id)
        report = workflow.save_topic(
            report, topic_id, findings=topic_findings(report, topic_id)
        )
    assert all(t["status"] == "ready" for t in report["workflow"]["topics"])
    return report


def reviews(report, revise=None):
    return [
        {
            "topic_id": item["id"],
            "verdict": "revise"
            if item["id"] == revise
            else "insufficient"
            if item["status"] in {"failed", "insufficient"}
            else "pass",
            "directionChecked": True,
            "scopeChecked": True,
            "causalityChecked": True,
            "note": "请补充解释边界，避免将披露差异直接解释为经营原因。"
            if item["id"] == revise
            else "合成流程核对已检查引用、归属及解释边界，缺口按状态保留。",
        }
        for item in report["workflow"]["topics"]
    ]


@pytest.mark.parametrize("period", ["2024年", "{{period:2024}}"])
def test_review_accepts_extracted_periods_without_rewriting_caller_input(period):
    report = ready_report()
    records = reviews(report)
    records[0]["note"] = f"{period}合并报表的方向、期间口径和解释依据已核对。"
    original = deepcopy(records)
    published = workflow.publish(workflow.review_report(report, records))
    assert published["workflow"]["status"] == "published"
    assert published["workflow"]["review"]["items"][0]["note"].startswith("2024年")
    assert records == original


@pytest.mark.parametrize(
    "note",
    ["1999年口径已核对。", "收入为2024元。", "增长率为12%。", "为{{fact:invented}}。"],
)
def test_review_still_rejects_unknown_periods_values_and_financial_references(note):
    report = ready_report()
    before = deepcopy(report)
    records = reviews(report)
    records[-1]["note"] = note
    with pytest.raises(SessionFileApiError, match="note 校验失败") as error:
        workflow.review_report(report, records)
    assert "2024" in str(error.value)
    assert "只修正报错专题" in str(error.value)
    assert report == before


@pytest.mark.parametrize("status", ["failed", "insufficient"])
def test_review_cannot_reopen_terminal_gap_and_rejection_is_atomic(status):
    report = ready_report()
    item = workflow.topic(report, "recurring")
    item.update(
        status=status, errorCode="MODEL_TIMEOUT", note="生成失败，保留有效发现。"
    )
    before = deepcopy(report)
    with pytest.raises(SessionFileApiError, match="不能通过复核重新启动修订"):
        workflow.review_report(report, reviews(report, revise="recurring"))
    assert report == before
    report = workflow.publish(workflow.review_report(report, reviews(report)))
    assert report["workflow"]["status"] == "published"
    assert workflow.topic(report, "recurring")["status"] == status
    assert workflow.topic(report, "recurring")["errorCode"] == "MODEL_TIMEOUT"
    assert report["findings"] == before["findings"]
    assert report["analysis"]["status"] == "partial"


def test_semantic_revision_budget_survives_reads_and_valid_saves():
    report = ready_report()
    facts, calculations = deepcopy(report["facts"]), deepcopy(report["calculations"])
    for attempt in (1, 2):
        report = workflow.review_report(report, reviews(report, revise="recurring"))
        item = workflow.topic(report, "recurring")
        assert item["reviewRevisionAttempts"] == attempt and item["failures"] == 0
        before = deepcopy(report)
        workflow.start_topic(report, "recurring")
        assert report == before
        next_step = workflow.next_action(report)
        assert next_step["tool"] == "save_financial_topic"
        assert next_step["arguments"]["topic_id"] == "recurring"
        finding = topic_findings(report, "recurring")[0]
        finding["section"] = "盈利质量"
        report = workflow.save_topic(report, "recurring", findings=[finding])
        assert workflow.topic(report, "recurring")["status"] == "ready"
        assert workflow.topic(report, "recurring")["reviewRevisionAttempts"] == attempt
    before = deepcopy(report)
    with pytest.raises(SessionFileApiError) as error:
        workflow.review_report(report, reviews(report, revise="recurring"))
    assert error.value.err_code == "REVIEW_REPAIR_EXHAUSTED"
    assert report == before and report["workflow"]["status"] == "draft"
    assert report["facts"] == facts and report["calculations"] == calculations
    report = workflow.start_topic(report, "recurring", retry=True)
    assert workflow.topic(report, "recurring")["reviewRevisionAttempts"] == 0


@pytest.mark.parametrize("identity", ["missing", "wrong", "ambiguous"])
def test_identity_inference_only_fills_unambiguous_missing_subject(identity):
    report = workflow.start_topic(comparison_report(), "operating")
    finding = topic_findings(report, "operating")[0]
    if identity == "ambiguous":
        finding = comparison_finding(report)
    if identity == "wrong":
        finding["subjectEntityId"] = next(
            e["id"]
            for e in report["comparison"]["entities"]
            if e["id"] != finding["subjectEntityId"]
        )
    else:
        finding["subjectEntityId"] = None
    before = deepcopy(finding)
    report = workflow.save_topic(report, "operating", findings=[finding])
    assert finding == before
    assert workflow.topic(report, "operating")["status"] == (
        "ready" if identity == "missing" else "needs_revision"
    )
