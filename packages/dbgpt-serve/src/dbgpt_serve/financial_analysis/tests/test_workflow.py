from copy import deepcopy
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    financial_completion_error,
    make_financial_tools,
)
from dbgpt_serve.financial_analysis.workflow import (
    TOPICS,
    public_snapshot,
    review_report,
)

from .test_agent_tools import payload
from .test_calculations import expanded_facts
from .test_runs import ALICE, BASE, extraction, upload


def finding(context, suffix=""):
    fact = context["data"]["facts"][0]
    if context["topic_id"] == "expenses":
        result = deepcopy(context["save_example"]["findings"][0])
        result["title"] += suffix
        return result
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


@pytest.mark.parametrize(
    "invalid",
    [
        {"directionChecked": False, "scopeChecked": False, "causalityChecked": False},
        {"directionChecked": "true"},
        {"verdict": "failed"},
        {"note": "缺少2019年的依据。"},
    ],
)
def test_review_feedback_identifies_the_topic_and_fields_without_changing_report(
    invalid,
):
    report = {
        "revision": "original",
        "workflow": {
            "status": "draft",
            "topics": [
                {"id": key, "status": "failed" if key == "cashflow" else "ready"}
                for key in TOPICS
            ],
        },
    }
    original = deepcopy(report)
    checked = reviews(report)
    checked[4].update(invalid)
    with pytest.raises(Exception) as error:
        review_report(report, checked)
    assert "cashflow" in str(error.value)
    assert all(key in str(error.value) for key in invalid)
    if "directionChecked" in invalid:
        assert "布尔 true" in str(error.value)
        assert "insufficient" in str(error.value)
    assert report == original


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
        if kind != "financial.progress":
            return
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
    assert client.get(
        f"{BASE}/{run}/exports/{export['id']}",
        headers=ALICE,
        params={"session_id": "s1"},
    ).json() == public_snapshot(old)
    assert events and events[-1][0] == "financial.progress"
    assert all(t["status"] == "completed" for t in events[-1][1]["tasks"])
    assert all(len(event[1]["tasks"]) == 4 for event in events)
    assert len({tuple(t["id"] for t in e[1]["tasks"]) for e in events}) == 1
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
        "revision": prepared["revision"],
    }
    assert prepared["next_action"]["tool"] == "save_financial_topic"
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
                f["id"].startswith("topic-cashflow-")
                for f in state["financial_report_context"]["findings"]
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
    assert checked["next_action"] is None
    assert checked["workflow"]["status"] == "published"
    failed = next(t for t in checked["workflow"]["topics"] if t["id"] == "cashflow")
    assert failed["status"] == "failed"
    assert state["financial_report_context"]["workflow"]["topics"][4]["completedAt"]
    final = payload(await publish(run, checked["revision"]))
    assert final["analysis"]["status"] == "partial" and final["next_action"] is None
    assert final["finding_count"] == 5 and len(calls) == 1
    assert await financial_completion_error(state, service=backend) is None


@pytest.mark.asyncio
async def test_direct_handoffs_partial_field_repair_and_compact_results(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = lambda path: dict(extraction(path), facts=expanded_facts())
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="report.pdf")],
    }
    prepare, publish, read, get_topic, save, review = make_financial_tools(
        state, service=backend
    )
    import json

    raw = json.loads(await prepare())
    assert "model_context" in raw
    assert "save_example" not in json.dumps(raw["chunks"])
    result = raw["model_context"]
    for key in TOPICS:
        context = result["topic_context"]
        assert context["topic_id"] == key
        valid = finding(context)
        drafts = [
            valid,
            dict(valid, summary="金额999元", unresolvedQuestions=["需要核查888元"]),
        ]
        if key == "operating":
            result = payload(
                await save(result["run_id"], result["revision"], key, drafts)
            )
            assert {x["field"] for x in result["topic_result"]["issues"]} == {
                "summary",
                "unresolvedQuestions[0]",
            }
            assert result["repair"]["draftFindings"][0] == valid
            result = payload(
                await save(
                    result["run_id"],
                    result["revision"],
                    key,
                    patches=[
                        {
                            "finding_index": 1,
                            "changes": {
                                "summary": valid["summary"],
                                "unresolvedQuestions": valid["unresolvedQuestions"],
                            },
                        }
                    ],
                )
            )
            assert (
                state["financial_report_context"]["workflow"]["topics"][0][
                    "draftFindings"
                ][0]
                == valid
            )
        else:
            result = payload(
                await save(result["run_id"], result["revision"], key, [valid])
            )
        assert "findings" not in result
        if key != "balance":
            assert "review_context" not in result
            assert result["next_action"]["tool"] == "save_financial_topic"
    assert len(result["review_context"]["findings"]) == 7
    report = state["financial_report_context"]
    result = payload(
        await review(result["run_id"], result["revision"], reviews(report))
    )
    assert result["workflow"]["status"] == "published"
    assert result["next_action"] is None and "review_context" not in result
    assert "findings" not in result
    assert len(payload(await read())["findings"]) == 7
    public = client.get(
        f"{BASE}/{result['run_id']}/report", headers=ALICE, params={"session_id": "s1"}
    ).json()["data"]
    assert all("draftFindings" not in item for item in public["workflow"]["topics"])
    assert state["financial_report_context"]["workflow"]["topics"][0]["draftFindings"]


def test_review_opinion_cannot_replace_backend_failure():
    from dbgpt_serve.financial_analysis import workflow

    from .test_analysis import report_fixture

    report = report_fixture()
    workflow.initialize(report)
    for item in report["workflow"]["topics"]:
        item.update(
            status="failed",
            note="后端格式校验失败",
            errorCode="FINDING_VALIDATION_FAILED",
            issues=[{"field": "summary", "code": "invalid_fields"}],
        )
    checked = reviews(report)
    checked[0]["note"] = "历史数据缺失。"
    workflow.review_report(report, checked)
    item = report["workflow"]["topics"][0]
    assert item["note"] == "后端格式校验失败"
    assert item["errorCode"] == "FINDING_VALIDATION_FAILED"
    assert item["review"]["note"] == "历史数据缺失。"


def test_rejected_drafts_never_appear_in_public_snapshots_or_exports():
    import json

    from dbgpt_serve.financial_analysis.exports import render_export

    report = {
        "findings": [],
        "workflow": {"topics": [{"draftFindings": [{"summary": "UNVALIDATED"}]}]},
    }
    assert "UNVALIDATED" not in json.dumps(public_snapshot(report))
    assert "UNVALIDATED" not in render_export(report, "json")
    assert report["workflow"]["topics"][0]["draftFindings"]


@pytest.mark.asyncio
async def test_available_expense_metrics_cannot_be_omitted(stack):
    client, serve = stack
    backend = serve.financial_analysis
    backend.extractor = lambda path: dict(extraction(path), facts=expanded_facts())
    state = {
        "owner_id": "alice",
        "conv_id": "s1",
        "session_files": [SimpleNamespace(file_id=upload(client), name="report.pdf")],
    }
    prepare, _, _, get_topic, save, _ = make_financial_tools(state, service=backend)
    prepared = payload(await prepare())
    context = payload(await get_topic(prepared["run_id"], "expenses"))
    item = finding(context)
    fact = context["data"]["facts"][0]
    item.update(
        factIds=[fact["id"]],
        evidenceExcerptIds=fact["evidenceExcerptIds"],
        summary=fact["reference"] + "，其余科目待核对。",
    )
    result = payload(
        await save(context["run_id"], context["revision"], "expenses", [item])
    )
    assert result["topic_result"]["saved"] is False
    assert result["topic_result"]["issues"][0]["code"] == "incomplete_topic_coverage"
    assert result["topic_result"]["issues"][0]["missing_metrics"]
    repaired = payload(
        await save(
            context["run_id"],
            result["revision"],
            "expenses",
            append_findings=[finding(context)],
        )
    )
    assert repaired["topic_result"]["saved"] is True
    stored = state["financial_report_context"]["workflow"]["topics"][3]
    assert stored["draftFindings"][0] == item
    assert len(stored["findingIds"]) == 2


@pytest.mark.parametrize("missing_code", ["research_expenses", "financial_expenses"])
def test_append_missing_expense_preserves_drafts_and_requires_full_validation(
    missing_code,
):
    from dbgpt_app.openapi.api_v1.tools.financial_tools import _topic_payload
    from dbgpt_serve.financial_analysis import workflow

    from .test_analysis import report_fixture

    report = report_fixture()
    report["analysis"] = {"status": "partial", "completedAt": None}
    report = workflow.start_topic(workflow.initialize(report), "expenses")
    context = _topic_payload(report, "expenses")
    facts = context["data"]["facts"]
    missing_ids = {f["id"] for f in report["facts"] if f["metricCode"] == missing_code}

    def make_draft(selected):
        result = finding(context)
        result.update(
            summary="、".join(f["reference"] for f in selected)
            + "，变动原因需核对附注。",
            factIds=[f["id"] for f in selected],
            evidenceExcerptIds=sorted(
                {e for f in selected for e in f["evidenceExcerptIds"]}
            ),
        )
        return result

    existing = make_draft([f for f in facts if f["id"] not in missing_ids])
    rejected = workflow.save_topic(report, "expenses", [existing])
    item = workflow.topic(rejected, "expenses")
    issue = item["issues"][0]
    assert issue["missing_metrics"] == [missing_code]
    assert {f["id"] for f in issue["missing_facts"]} == missing_ids
    assert "append_findings" in issue["hint"]
    supplement = make_draft([f for f in facts if f["id"] in missing_ids])
    invalid = dict(supplement, summary="新增费用999亿元")
    failed = workflow.save_topic(
        deepcopy(rejected), "expenses", append_findings=[invalid]
    )
    assert workflow.topic(failed, "expenses")["status"] == "needs_revision"
    assert failed["findings"] == []
    saved = workflow.save_topic(
        deepcopy(rejected), "expenses", append_findings=[supplement]
    )
    assert workflow.topic(saved, "expenses")["status"] == "ready"
    assert workflow.topic(saved, "expenses")["draftFindings"] == [existing, supplement]
    assert len(saved["findings"]) == 2
    assert saved["workflow"]["review"] is None
    # Existing declared calculation shorthand also counts as actual coverage.
    calculation = next(
        c
        for c in context["data"]["calculations"]
        if set(c["inputFactIds"]) & missing_ids
    )
    shorthand = dict(
        supplement,
        summary="{{" + calculation["id"] + "}}，变动原因需核对。",
        factIds=[],
        calculationIds=[calculation["id"]],
    )
    accepted_shorthand = workflow.save_topic(
        deepcopy(rejected), "expenses", append_findings=[shorthand]
    )
    assert workflow.topic(accepted_shorthand, "expenses")["status"] == "ready"
    # Adding an unused ID without discussing the metric does not pass coverage.
    stuffed = deepcopy(existing)
    stuffed["factIds"] += supplement["factIds"]
    still_missing = workflow.save_topic(deepcopy(rejected), "expenses", [stuffed])
    assert (
        workflow.topic(still_missing, "expenses")["issues"][0]["code"]
        == "incomplete_topic_coverage"
    )
    with pytest.raises(Exception, match="不同时传 findings"):
        workflow.save_topic(
            deepcopy(rejected), "expenses", [existing], append_findings=[supplement]
        )
