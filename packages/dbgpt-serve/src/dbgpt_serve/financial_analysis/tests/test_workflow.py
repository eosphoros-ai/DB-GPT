from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    financial_completion_error,
    make_financial_tools,
)
from dbgpt_serve.financial_analysis.workflow import TOPICS

from .test_agent_tools import payload
from .test_calculations import expanded_facts
from .test_runs import ALICE, BASE, extraction, upload


def finding(context, suffix=""):
    fact = context["data"]["facts"][0]
    return {
        "section": context["section"],
        "title": "数据观察" + suffix,
        "summary": fact["reference"] + "，变化原因仍需结合附注核对。",
        "supportStatus": "partial",
        "factIds": [fact["id"]],
        "calculationIds": [],
        "evidenceExcerptIds": fact["evidenceExcerptIds"],
        "counterEvidence": [],
        "unresolvedQuestions": ["需核对附注中的变化原因。"],
    }


def reviews(report):
    return [
        {
            "topic_id": topic["id"],
            "verdict": "pass"
            if topic["status"] in {"ready", "reviewed"}
            else "insufficient",
            "directionChecked": True,
            "scopeChecked": True,
            "causalityChecked": True,
            "note": "已核对引用及比较口径，未据此断言具体变化原因。",
        }
        for topic in report["workflow"]["topics"]
    ]


@pytest.mark.asyncio
async def test_sectional_agent_progress_review_retry_versions_and_scope(stack):
    client, serve = stack
    backend = serve.financial_analysis
    calls = []

    def extract(path):
        calls.append(path)
        return dict(extraction(path), facts=expanded_facts())

    backend.extractor = extract
    backend.analyzer = lambda *args: pytest.fail("No nested analysis model")
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="年报.pdf")],
    }
    events = []

    async def progress(kind, body):
        events.append((kind, body))

    prepare, publish, read, get_topic, save, review = make_financial_tools(
        state, service=backend, stream_callback=progress
    )
    prepared = payload(await prepare())
    run = prepared["run_id"]
    with pytest.raises(Exception, match="复核"):
        await publish(run, prepared["revision"])
    for key in TOPICS:
        context = payload(await get_topic(run, key))
        saved = payload(
            await save(
                run,
                context["revision"],
                key,
                [finding(context), finding(context, "补充")],
            )
        )
        assert saved["workflow"]["topics"][list(TOPICS).index(key)]["status"] == "ready"
    report = state["financial_report_context"]
    assert (
        len(report["findings"]) == 12
    )  # Per-topic validation, not a whole-report six-item cap.
    with pytest.raises(Exception, match="全部专题"):
        await review(run, report["revision"], reviews(report)[:-1])
    checked = reviews(report)
    checked[0].update(verdict="revise", note="请进一步区分观察结果与变化原因。")
    result = payload(await review(run, report["revision"], checked))
    with pytest.raises(Exception, match="修订"):
        await publish(run, result["revision"])
    context = payload(await get_topic(run, "operating"))
    await save(run, context["revision"], "operating", [finding(context)])
    report = state["financial_report_context"]
    checked = payload(await review(run, report["revision"], reviews(report)))
    published = payload(await publish(run, checked["revision"]))
    assert published["analysis"]["status"] == "completed"
    assert await financial_completion_error(state, service=backend) is None
    refresh = payload(await get_topic(run, "expenses"))
    assert refresh["revision"] == published["revision"]
    assert refresh["next_action"] is None
    assert await financial_completion_error(state, service=backend) is None
    assert backend.get("alice", "s1", run)["stage"] == "completed"
    old = backend.get("alice", "s1", run, report=True)
    export = client.post(
        f"{BASE}/{run}/exports",
        headers=ALICE,
        json={"session_id": "s1", "revision": old["revision"], "format": "json"},
    ).json()["data"]
    context = payload(await get_topic(run, "expenses", retry=True))
    assert "review" not in state["financial_report_context"]["workflow"]["topics"][3]
    with pytest.raises(Exception, match="报告已更新"):
        await save(run, old["revision"], "expenses", [finding(context)])
    for _ in range(3):
        result = payload(
            await save(
                run,
                context["revision"],
                "expenses",
                [dict(finding(context), summary="费用增加999元")],
            )
        )
        context["revision"] = result["revision"]
    topic = next(t for t in result["workflow"]["topics"] if t["id"] == "expenses")
    assert topic["status"] == "failed"
    assert backend.get("alice", "s1", run, report=True)["findings"] == old["findings"]
    assert len(calls) == 1  # A topic retry must never extract the PDF again.
    context = payload(await get_topic(run, "expenses", retry=True))
    await save(run, context["revision"], "expenses", [finding(context, "修订")])
    report = state["financial_report_context"]
    await review(run, report["revision"], reviews(report))
    await publish(run, state["financial_report_context"]["revision"])
    assert len(state["financial_report_context"]["workflow"]["history"]) == 2
    unchanged = [
        f for f in old["findings"] if not f["id"].startswith("topic-expenses-")
    ]
    assert [
        f
        for f in state["financial_report_context"]["findings"]
        if not f["id"].startswith("topic-expenses-")
    ] == unchanged
    assert (
        client.get(
            f"{BASE}/{run}/exports/{export['id']}",
            headers=ALICE,
            params={"session_id": "s1"},
        ).json()
        == old
    )
    assert events and events[-1][0] == "financial.progress"
    assert all(t["status"] == "completed" for t in events[-1][1]["tasks"])
    assert len(events[-1][1]["tasks"]) == 13
    for owner, session in [("bob", "s1"), ("alice", "foreign")]:
        with pytest.raises(Exception):
            backend.update_agent_workflow(
                owner,
                session,
                run,
                report["revision"],
                "start",
                topic_id="expenses",
                retry=True,
            )


@pytest.mark.asyncio
async def test_topic_missing_data_and_cross_topic_findings_are_explicit(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = extraction
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="年报.pdf")],
    }
    prepare, publish, read, get_topic, save, review = make_financial_tools(
        state, service=backend
    )
    prepared = payload(await prepare())
    run = prepared["run_id"]
    for key in TOPICS:
        context = payload(await get_topic(run, key))
        missing = context["missingRequiredMetrics"]
        if missing:
            await save(
                run,
                context["revision"],
                key,
                [],
                "缺少本专题必要科目，无法形成可靠比较。",
            )
        else:
            with pytest.raises(Exception, match="不能用空结论"):
                await save(run, context["revision"], key, [], "资料不足")
            await save(run, context["revision"], key, [finding(context)])
    report = state["financial_report_context"]
    assert {
        t["id"] for t in report["workflow"]["topics"] if t["status"] == "insufficient"
    } == {"margins", "expenses"}
    await review(run, report["revision"], reviews(report))
    final = payload(await publish(run, state["financial_report_context"]["revision"]))
    assert final["analysis"]["status"] == "partial"
    context = payload(await get_topic(run, "operating", retry=True))
    bad = finding(context)
    bad.update(section="balance")
    rejected = payload(await save(run, context["revision"], "operating", [bad]))
    assert rejected["workflow"]["topics"][0]["status"] == "needs_revision"


@pytest.mark.asyncio
async def test_mixed_topic_repair_refresh_and_failed_topic_can_finish_partial(stack):
    client, serve = stack
    backend = serve.financial_analysis
    calls = []

    def extract(path):
        calls.append(path)
        return dict(extraction(path), facts=expanded_facts())

    backend.extractor = extract
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="年报.pdf")],
    }
    prepare, publish, read, get_topic, save, review = make_financial_tools(
        state, service=backend
    )
    prepared = payload(await prepare())
    run = prepared["run_id"]
    assert prepared["next_action"]["arguments"] == {
        "run_id": run,
        "topic_id": "operating",
    }
    for key in TOPICS:
        context = payload(await get_topic(run, key))
        if key != "cashflow":
            await save(**context["save_example"])
            continue
        refreshed = payload(await get_topic(run, key, retry=True))
        assert refreshed["revision"] == context["revision"]
        valid = finding(context)
        invalid = dict(valid, counterEvidence=["低于1倍"])
        for attempt in range(3):
            result = payload(
                await save(run, context["revision"], key, [valid, invalid])
            )
            assert result["topic_result"]["saved"] is False
            assert result["topic_result"]["issues"][0]["finding_index"] == 1
            assert result["topic_result"]["issues"][0]["field"] == "counterEvidence[0]"
            assert not any(
                f["id"].startswith("topic-cashflow-") for f in result["findings"]
            )
            context["revision"] = result["revision"]
            if attempt < 2:
                assert result["next_action"]["tool"] == "save_financial_topic"
                assert (
                    result["next_action"]["arguments"]["revision"] == result["revision"]
                )
                refreshed = payload(await get_topic(run, key, retry=True))
                assert refreshed["revision"] == result["revision"]
                item = state["financial_report_context"]["workflow"]["topics"][4]
                assert item["failures"] == attempt + 1 and item["attempts"] == 1
            else:
                assert result["topic_result"]["status"] == "failed"
                assert result["next_action"]["arguments"]["topic_id"] == "balance"
    report = state["financial_report_context"]
    assert "review_financial_report" in await financial_completion_error(
        state, service=backend
    )
    checked = payload(await review(run, report["revision"], reviews(report)))
    assert checked["next_action"]["tool"] == "publish_financial_report"
    failed = next(t for t in checked["workflow"]["topics"] if t["id"] == "cashflow")
    assert failed["status"] == "failed" and failed["completedAt"]
    final = payload(await publish(**checked["next_action"]["arguments"]))
    assert final["analysis"]["status"] == "partial" and final["next_action"] is None
    assert len(final["findings"]) == 5 and len(calls) == 1
    assert await financial_completion_error(state, service=backend) is None
