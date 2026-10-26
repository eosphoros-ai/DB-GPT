import asyncio
import json
from copy import deepcopy

import pytest

from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.analysis import review_model_context
from dbgpt_serve.financial_analysis.parallel import (
    analyze_topics,
    concurrency_limit,
    generate_topic,
)
from dbgpt_serve.financial_analysis.progress import public_progress

from .conftest import wait_ready
from .test_comparison_analysis import comparison_finding, comparison_report
from .test_comparison_service import create


def test_review_keeps_claim_dependencies_scope_and_missing_data_inventory():
    report = workflow.start_topic(comparison_report(), "operating")
    report = workflow.save_topic(
        report, "operating", findings=[comparison_finding(report)]
    )
    before = deepcopy(report)
    context = review_model_context(report)
    calculation = context["calculations"][0]
    assert {f["id"] for f in context["facts"]} == set(calculation["inputFactIds"])
    assert {f["entityId"] for f in context["facts"]} == {
        calculation["subjectEntityId"],
        calculation["baselineEntityId"],
    }
    assert all(f["statementScope"] and f["unit"] for f in context["facts"])
    assert {e["id"] for e in context["evidence"]} == {
        i for f in context["facts"] for i in f["evidenceExcerptIds"]
    }
    assert any(
        "total_assets" in item["metricCodes"] for item in context["availableMetrics"]
    )
    assert any(
        "gross_margin" in item["calculationCodes"]
        for item in context["availableCalculations"]
    )
    assert "findingReferenceTemplates" not in context
    assert all("sourceCells" not in e for e in context["evidence"])
    assert len(json.dumps(context, ensure_ascii=False)) < 16000
    assert report == before


@pytest.mark.asyncio
async def test_timeout_retains_only_valid_findings_and_remains_failed(isolated_service):
    service, _, _, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    snapshot = service.begin_parallel_topics(
        "alice", "scope", run_id, report["revision"], 6
    )
    valid = comparison_finding(snapshot)
    invalid = dict(valid, subjectEntityId=None)
    calls = 0

    async def generate(context):
        nonlocal calls
        calls += 1
        if calls == 1:
            return json.dumps({"findings": [valid, invalid]})
        assert context["repair"]["issues"]
        raise asyncio.TimeoutError

    result = await generate_topic(snapshot, "operating", generate)
    assert calls == 2 and result.error == "MODEL_TIMEOUT"
    assert len(result.findings) == 1
    report = service.merge_parallel_topic("alice", "scope", run_id, result)
    item = workflow.topic(report, "operating")
    assert item["status"] == "failed" and item["errorCode"] == "MODEL_TIMEOUT"
    assert len(item["findingIds"]) == len(report["findings"]) == 1
    assert report["workflow"]["status"] == "draft"
    assert snapshot["findings"] == []


@pytest.mark.asyncio
async def test_default_starts_all_topics_within_global_slots(
    isolated_service, monkeypatch
):
    monkeypatch.delenv("DBGPT_FINANCIAL_CONCURRENCY", raising=False)
    service, _, _, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    started = set()
    phases = []
    barrier = asyncio.Event()

    async def generate(context):
        started.add(context["topic_id"])
        if len(started) == len(workflow.TOPICS):
            barrier.set()
        await barrier.wait()
        raise RuntimeError("synthetic provider failure")

    async def activity(value):
        phases.append(value)

    result = await asyncio.wait_for(
        analyze_topics(service, "alice", "scope", report, generate, activity=activity),
        5,
    )
    assert started == set(workflow.TOPICS)
    assert any(len(value["topics"]) == 6 for value in phases)
    assert result["workflow"]["parallelBatch"]["status"] == "completed"
    assert all(
        t["errorCode"] == "MODEL_REQUEST_FAILED" for t in result["workflow"]["topics"]
    )
    assert service.parallel_topic_slots._value == 6


@pytest.mark.parametrize(
    "configured,expected", [("2", 2), ("99", 6), ("0", 1), ("invalid", 6)]
)
def test_concurrency_configuration_remains_bounded(monkeypatch, configured, expected):
    monkeypatch.setenv("DBGPT_FINANCIAL_CONCURRENCY", configured)
    assert concurrency_limit() == expected


def test_progress_names_real_work_and_discloses_incomplete_publication():
    report = comparison_report()
    for item in report["workflow"]["topics"]:
        item["status"] = "running"
    workflow.topic(report, "operating")["status"] = "ready"
    workflow.topic(report, "balance")["status"] = "failed"
    tasks = public_progress(report, activity={"topics": {"cashflow": "repairing"}})
    assert "经营表现" in tasks[1]["detail"]
    assert "正在修正结论与引用：现金流" in tasks[1]["detail"]
    assert "尚待补充" in tasks[1]["detail"]
    assert "已保存" not in tasks[1]["detail"]
    assert tasks[2]["status"] == "pending"
    for item in report["workflow"]["topics"]:
        if item["status"] != "failed":
            item["status"] = "reviewed"
    report["workflow"].update(status="published", review={"items": []})
    final = public_progress(report, previous=tasks)
    assert all(t["status"] == "completed" for t in final)
    assert "未完成的分析已在对应章节说明" in final[-1]["detail"]
    assert final[1]["startedAt"] == tasks[1]["startedAt"]
