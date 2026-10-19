import asyncio
import json
import threading
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import make_financial_tools
from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.parallel import (
    analyze_topics,
    concurrency_limit,
    generate_topic,
)
from dbgpt_serve.financial_analysis.service import FinancialAnalysisService

from .test_agent_tools import payload
from .test_calculations import expanded_facts
from .test_runs import extraction, upload, wait_run
from .test_workflow import reviews


def valid(context):
    facts = context["data"]["facts"]
    if context["topic_id"] == "expenses":
        facts = [f for f in facts if f["fiscalPeriod"] == context["data"]["year"]]
    else:
        facts = facts[:1]
    return {
        "section": context["section"],
        "title": "财务变化与限制",
        "summary": "、".join(f["reference"] for f in facts) + "，需结合附注核对原因。",
        "supportStatus": "partial",
        "factIds": [f["id"] for f in facts],
        "calculationIds": [],
        "evidenceExcerptIds": sorted(
            {e for f in facts for e in f["evidenceExcerptIds"]}
        ),
        "counterEvidence": [],
        "unresolvedQuestions": ["需核对变化原因。"],
    }


def fresh(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = lambda path: dict(extraction(path), facts=expanded_facts())
    run = str(uuid4())
    backend.create(
        "alice", "s1", upload(client), run, agent_model="test", sectional=True
    )
    wait_run(client, run)
    return backend, backend.get("alice", "s1", run, report=True)


@pytest.mark.asyncio
async def test_bounded_generation_and_validation_merge_without_lost_updates(
    stack, monkeypatch
):
    backend, report = fresh(stack)
    original = deepcopy(report)
    gate = asyncio.Event()
    active = peak = 0
    # The first three validators must actually overlap on distinct threads.
    barrier = threading.Barrier(3, timeout=5)
    validator = workflow.save_topic
    validation_count = 0
    count_lock = threading.Lock()

    def validate(*args, **kwargs):
        nonlocal validation_count
        with count_lock:
            validation_count += 1
            count = validation_count
        if count <= 3:
            barrier.wait()
        return validator(*args, **kwargs)

    monkeypatch.setattr(workflow, "save_topic", validate)

    async def generate(context):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 3:
            gate.set()
        await gate.wait()
        await asyncio.sleep(0)
        active -= 1
        return json.dumps({"findings": [valid(context)]}, ensure_ascii=False)

    final = await analyze_topics(
        backend, "alice", "s1", report, generate, concurrency=3
    )
    assert peak == 3 and validation_count == 6  # no duplicate serial validation
    assert report == original  # worker snapshots did not mutate caller data
    assert final["facts"] == original["facts"]
    assert len(final["findings"]) == 6
    assert [f["id"] for f in final["findings"]] == [
        f"topic-{t}-1" for t in workflow.TOPICS
    ]
    assert all(t["status"] == "ready" for t in final["workflow"]["topics"])
    assert final["workflow"]["status"] == "draft"  # review remains mandatory
    assert final["workflow"]["parallelBatch"]["pending"] == []
    final = backend.update_agent_workflow(
        "alice",
        "s1",
        report["report"]["run"]["id"],
        final["revision"],
        "review",
        reviews=reviews(final),
    )
    assert final["workflow"]["status"] == "published"


@pytest.mark.asyncio
async def test_partial_failures_patch_preservation_and_timeout(stack):
    backend, report = fresh(stack)
    calls = {}

    async def generate(context):
        key = context["topic_id"]
        calls[key] = calls.get(key, 0) + 1
        if key == "cashflow":
            await asyncio.Event().wait()
        if key == "balance":
            raise RuntimeError("secret provider detail")
        finding = valid(context)
        if key == "operating":
            if calls[key] == 1:
                return json.dumps(
                    {"findings": [finding, dict(finding, summary="999亿元")]}
                )
            assert context["repair"]["draftFindings"][0] == finding
            return json.dumps(
                {
                    "patches": [
                        {"finding_index": 1, "changes": {"summary": finding["summary"]}}
                    ]
                }
            )
        return json.dumps({"findings": [finding]})

    final = await analyze_topics(backend, "alice", "s1", report, generate, timeout=0.2)
    assert workflow.topic(final, "operating")["saveAttempts"] == 2
    assert len(workflow.topic(final, "operating")["findingIds"]) == 2
    assert workflow.topic(final, "cashflow")["errorCode"] == "MODEL_TIMEOUT"
    assert workflow.topic(final, "balance")["errorCode"] == "MODEL_REQUEST_FAILED"
    assert "secret" not in json.dumps(final)
    final = backend.update_agent_workflow(
        "alice",
        "s1",
        report["report"]["run"]["id"],
        final["revision"],
        "review",
        reviews=reviews(final),
    )
    assert final["analysis"]["status"] == "partial"


@pytest.mark.asyncio
async def test_duplicate_late_result_scope_and_busy_revision(stack):
    backend, report = fresh(stack)
    run = report["report"]["run"]["id"]
    snapshot = backend.begin_parallel_topics("alice", "s1", run, report["revision"], 3)

    async def generate(context):
        return json.dumps({"findings": [valid(context)]})

    result = await generate_topic(snapshot, "operating", generate)
    for owner, session in [("bob", "s1"), ("alice", "other")]:
        with pytest.raises(Exception):
            backend.merge_parallel_topic(owner, session, run, result)
    with pytest.raises(Exception, match="并发"):
        backend.update_agent_workflow(
            "alice",
            "s1",
            run,
            snapshot["revision"],
            "start",
            topic_id="operating",
            retry=True,
        )
    merged = backend.merge_parallel_topic("alice", "s1", run, result)
    with pytest.raises(Exception, match="过期"):
        backend.merge_parallel_topic("alice", "s1", run, result)
    backend.abort_parallel_topics("alice", "s1", run, result.batch_id)
    with pytest.raises(Exception, match="过期"):
        backend.merge_parallel_topic("alice", "s1", run, result)
    current = backend.get("alice", "s1", run, report=True)
    assert current["findings"] == merged["findings"]
    assert workflow.topic(current, "recurring")["status"] == "needs_revision"


@pytest.mark.asyncio
async def test_cancellation_and_restart_invalidate_batch(stack):
    backend, report = fresh(stack)
    started = asyncio.Event()

    async def blocked(context):
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(analyze_topics(backend, "alice", "s1", report, blocked))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    run = report["report"]["run"]["id"]
    current = backend.get("alice", "s1", run, report=True)
    assert current["workflow"]["parallelBatch"]["status"] == "interrupted"
    assert not any(t["status"] == "running" for t in current["workflow"]["topics"])
    backend, report = fresh(stack)
    run = report["report"]["run"]["id"]
    snapshot = backend.begin_parallel_topics("alice", "s1", run, report["revision"], 3)

    async def generate(context):
        return json.dumps({"findings": [valid(context)]})

    result = await generate_topic(snapshot, "operating", generate)
    recovered = FinancialAnalysisService(backend.registry)
    try:
        with pytest.raises(Exception, match="过期"):
            recovered.merge_parallel_topic("alice", "s1", run, result)
    finally:
        recovered.close()


@pytest.mark.asyncio
async def test_prepare_hands_parallel_result_to_explicit_review(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = lambda path: dict(extraction(path), facts=expanded_facts())
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="report.pdf")],
    }

    async def generate(context):
        return json.dumps({"findings": [valid(context)]})

    prepare, _, _, _, _, review = make_financial_tools(
        state, service=backend, topic_generator=generate
    )
    prepared = payload(await prepare())
    assert prepared["next_action"]["tool"] == "review_financial_report"
    assert len(prepared["review_context"]["findings"]) == 6
    report = state["financial_report_context"]
    assert payload(await prepare())["revision"] == report["revision"]
    result = payload(
        await review(prepared["run_id"], report["revision"], reviews(report))
    )
    assert result["workflow"]["status"] == "published"


@pytest.mark.asyncio
async def test_prepare_emits_live_feedback_before_model_returns_and_persists_stages(
    stack,
):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = lambda path: dict(extraction(path), facts=expanded_facts())
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="report.pdf")],
    }
    events = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def stream(kind, body):
        if kind == "financial.execution":
            assert body["action"] in {
                "prepare_financial_report",
                "review_financial_report",
            }
            return
        events.append(deepcopy(body["tasks"]))

    async def generate(context):
        entered.set()
        await release.wait()
        return json.dumps({"findings": [valid(context)]})

    prepare, _, _, _, _, review = make_financial_tools(
        state, service=backend, topic_generator=generate, stream_callback=stream
    )
    pending = asyncio.create_task(prepare())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert not pending.done()
        assert "等待模型返回" in events[-1][1]["detail"]
        assert events[-1][1]["status"] == "in_progress"
    finally:
        release.set()
        prepared = payload(await pending)
    assert any("校验数字" in e[1]["detail"] for e in events)
    assert events[-1][2]["status"] == "in_progress"
    report = state["financial_report_context"]
    await review(prepared["run_id"], report["revision"], reviews(report))
    assert all(len(e) == 4 for e in events)
    assert all(t["status"] == "completed" for t in events[-1])
    assert state["financial_plan"] == events[-1]


@pytest.mark.parametrize("value,expected", [("0", 1), ("100", 6), ("bad", 3), ("2", 2)])
def test_concurrency_configuration_is_bounded(monkeypatch, value, expected):
    monkeypatch.setenv("DBGPT_FINANCIAL_CONCURRENCY", value)
    assert concurrency_limit() == expected


@pytest.mark.asyncio
async def test_malformed_repair_does_not_lose_previous_draft(stack):
    backend, report = fresh(stack)
    snapshot = backend.begin_parallel_topics(
        "alice", "s1", report["report"]["run"]["id"], report["revision"], 3
    )
    count = 0

    async def generate(context):
        nonlocal count
        count += 1
        finding = valid(context)
        if count == 1:
            return json.dumps({"findings": [finding, dict(finding, summary="999亿元")]})
        assert context["repair"]["draftFindings"][0] == finding
        if count == 2:
            return "{broken-json"
        return json.dumps(
            {
                "patches": [
                    {"finding_index": 1, "changes": {"summary": finding["summary"]}}
                ]
            }
        )

    result = await generate_topic(snapshot, "operating", generate)
    assert result.topic["status"] == "ready"
    assert len(result.findings) == 2
    assert result.metrics["modelCalls"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_reference", [False, True])
async def test_section_routing_is_deterministic_but_fact_scope_stays_strict(
    stack, foreign_reference
):
    backend, report = fresh(stack)
    snapshot = backend.begin_parallel_topics(
        "alice", "s1", report["report"]["run"]["id"], report["revision"], 3
    )

    async def generate(context):
        finding = valid(context)
        finding["section"] = "profitability"
        if foreign_reference:
            finding["factIds"].append(
                next(f["id"] for f in report["facts"] if f["metricCode"] == "inventory")
            )
        return json.dumps({"findings": [finding]})

    result = await generate_topic(snapshot, "operating", generate)
    assert result.topic["status"] == ("failed" if foreign_reference else "ready")
    if not foreign_reference:
        assert result.findings[0]["sectionKey"] == "overview"
        assert result.metrics["modelCalls"] == 1


@pytest.mark.asyncio
async def test_cancelled_validation_thread_cannot_commit_later(stack, monkeypatch):
    backend, report = fresh(stack)
    entered, release = threading.Event(), threading.Event()
    validator = workflow.save_topic

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return validator(*args, **kwargs)

    monkeypatch.setattr(workflow, "save_topic", blocked)

    async def generate(context):
        return json.dumps({"findings": [valid(context)]})

    task = asyncio.create_task(analyze_topics(backend, "alice", "s1", report, generate))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        before = backend.get("alice", "s1", report["report"]["run"]["id"], report=True)
        release.set()
        await asyncio.sleep(0.05)
        assert (
            backend.get("alice", "s1", report["report"]["run"]["id"], report=True)
            == before
        )
        assert before["findings"] == []
    finally:
        release.set()


@pytest.mark.asyncio
async def test_global_slots_bound_multiple_reports(stack):
    backend, first = fresh(stack)
    _, second = fresh(stack)
    active = peak = 0
    gate = asyncio.Event()

    async def generate(context):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 6:
            gate.set()
        await asyncio.wait_for(gate.wait(), 5)
        await asyncio.sleep(0)
        active -= 1
        return json.dumps({"findings": [valid(context)]})

    results = await asyncio.gather(
        *[
            analyze_topics(backend, "alice", "s1", r, generate, concurrency=6)
            for r in (first, second)
        ]
    )
    assert peak == 6
    assert all(len(r["findings"]) == 6 for r in results)


@pytest.mark.asyncio
async def test_parallel_expense_repair_can_append_without_rewriting(stack):
    backend, report = fresh(stack)
    snapshot = backend.begin_parallel_topics(
        "alice", "s1", report["report"]["run"]["id"], report["revision"], 3
    )
    count = 0
    existing = None

    async def generate(context):
        nonlocal count, existing
        count += 1
        if count == 1:
            partial = deepcopy(context)
            missing = {
                f["id"]
                for f in report["facts"]
                if f["metricCode"] == "research_expenses"
            }
            partial["data"]["facts"] = [
                f for f in context["data"]["facts"] if f["id"] not in missing
            ]
            existing = valid(partial)
            return json.dumps({"findings": [existing]})
        issue = context["repair"]["issues"][0]
        assert issue["missing_metrics"] == ["research_expenses"]
        assert context["repair"]["draftFindings"] == [existing]
        supplement = deepcopy(context)
        supplement["data"]["facts"] = issue["missing_facts"]
        return json.dumps({"append_findings": [valid(supplement)]})

    result = await generate_topic(snapshot, "expenses", generate)
    assert result.topic["status"] == "ready"
    assert result.metrics["modelCalls"] == 2
    assert result.topic["draftFindings"][0] == existing
    assert len(result.findings) == 2
