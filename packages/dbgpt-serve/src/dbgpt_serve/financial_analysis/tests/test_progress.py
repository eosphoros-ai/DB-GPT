from copy import deepcopy

import pytest

from dbgpt_serve.financial_analysis.progress import public_progress


def report(statuses, **flow):
    return {
        "facts": [{}, {}],
        "calculations": [{}],
        "findings": [{}, {}],
        "workflow": {"topics": [{"status": s} for s in statuses], **flow},
    }


def test_fixed_stages_through_extraction_analysis_review_and_partial_publication():
    states = [
        public_progress(stage="extract"),
        public_progress(stage="calculate"),
        public_progress(stage="save"),
        public_progress(report(["running", "pending"])),
        public_progress(report(["ready", "failed"])),
        public_progress(report(["reviewed", "failed"], review={})),
        public_progress(report(["reviewed", "failed"], status="published")),
    ]
    assert all(len(s) == 4 for s in states)
    assert len({tuple(t["id"] for t in s) for s in states}) == 1
    assert [sum(t["status"] == "completed" for t in s) for s in states] == [
        0,
        0,
        0,
        1,
        2,
        2,
        4,
    ]
    assert all(t["status"] != "cancelled" for s in states for t in s)
    assert "专题" not in str(states) and "失败" not in str(states)


def test_review_and_retry_keep_stage_identity_without_claiming_completed_report():
    prior = public_progress(
        report(["reviewed"], review={"ok": True}, status="published")
    )
    prior[1]["startedAt"] = "2000-01-01T00:00:00+00:00"
    reopened = public_progress(report(["running"]), previous=prior)
    assert [t["status"] for t in reopened] == [
        "completed",
        "in_progress",
        "pending",
        "pending",
    ]
    assert reopened[1]["startedAt"] != prior[1]["startedAt"]
    assert "finishedAt" not in reopened[1]
    checking = public_progress(report(["reviewed"], review={"ok": True}))
    assert checking[3]["status"] == "in_progress"


@pytest.mark.parametrize("data", [None, report(["running"])])
def test_interruption_retains_four_stages_and_never_says_all_complete(data):
    tasks = public_progress(data, error=True)
    assert len(tasks) == 4
    assert sum(t["status"] == "error" for t in tasks) == 1
    assert tasks[-1]["status"] == "pending"


def test_activity_is_execution_feedback_without_mutating_report_or_exposing_drafts():
    data = report(["running"])
    original = deepcopy(data)
    first = public_progress(data, activity={"generating": 3})
    second = public_progress(
        data, previous=first, activity={"validating": 1, "repairing": 2}
    )
    assert "等待模型返回" in first[1]["detail"]
    assert "已保存 2 条" in second[1]["detail"]
    assert "校验数字" in second[1]["detail"] and "修正" in second[1]["detail"]
    assert first[1]["startedAt"] == second[1]["startedAt"]
    assert data == original
