import json

from dbgpt_app.openapi.api_v1.financial_execution import (
    FinancialExecutionStream,
    interrupt_financial_progress,
)
from dbgpt_app.openapi.api_v1.react_prompt import build_react_prompt_template
from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    _result,
    financial_execution_guidance,
)
from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.tests.test_comparison_analysis import (
    comparison_finding,
    comparison_report,
)


def test_stage_log_keeps_clock_and_does_not_replay_finished_stages():
    clock = [10.0]
    stream = FinancialExecutionStream([], clock=lambda: clock[0])
    stream.start(1, "prepare", "prepare_financial_comparison", {}, "读取财报")
    tasks = [
        {
            "id": "financial-read",
            "content": "读取财报",
            "status": "completed",
            "detail": "已提取财务数据。",
        }
    ]
    clock[0] = 40.0
    assert "[00:30]" in stream.progress(1, tasks)[0]["content"]
    stream.finish(1, {"outputs": [], "status": "completed"})
    clock[0] = 140.0
    stream.start(2, "review", "review_financial_report", {}, "核对结论")
    assert stream.progress(2, tasks) == []
    tasks.append(
        {
            "id": "financial-review",
            "content": "核对结论",
            "status": "completed",
            "detail": "已完成结论核对。",
        }
    )
    events = stream.progress(2, tasks)
    assert len(events) == 1 and "[02:10]" in events[0]["content"]


def test_prepare_returns_direct_review_context_below_tool_storage_threshold():
    report = comparison_report()
    report = workflow.start_topic(report, "operating")
    report = workflow.save_topic(
        report, "operating", findings=[comparison_finding(report)]
    )
    for item in report["workflow"]["topics"]:
        if item["status"] == "pending":
            item.update(status="failed", errorCode="MODEL_TIMEOUT")
    result = _result(report, "scope", include_context=True)
    context = json.loads(result)["model_context"]
    assert context["next_action"]["tool"] == "review_financial_report"
    assert context["review_context"]["findings"] == report["findings"]
    assert context["review_context"]["data"]["calculations"]
    assert len(result) < 50000


def test_native_prompt_does_not_require_conflicting_text_action_protocol():
    template = build_react_prompt_template("workflow", financial_enabled=False)
    params = {
        "action_space": "tool descriptions",
        "action_space_names": "add, terminate",
    }
    native = template.format(**params, native_function_calling=True)
    assert "Invoke the supplied native functions" in native
    assert "Every response must contain exactly one Action" not in native
    text = template.format(**params, native_function_calling=False)
    assert "Every response must contain exactly one Action and one Action Input" in text


def test_review_guidance_survives_missing_memory_without_fabricating_reviews():
    report = comparison_report()
    for topic in report["workflow"]["topics"]:
        topic.update(status="failed", errorCode="MODEL_TIMEOUT")
    state = {"financial_report_context": report}
    guidance = financial_execution_guidance(state)
    assert "review_financial_report" in guidance
    assert report["revision"] in guidance
    assert report["report"]["run"]["id"] in guidance
    assert "不回到 prepare" in guidance
    assert '"reviews":' not in guidance
    assert report["workflow"]["status"] == "draft"


def test_interruption_ends_active_stage_but_preserves_completed_work_and_draft():
    state = {
        "financial_plan": [
            {"id": "read", "status": "completed", "finishedAt": "saved"},
            {"id": "review", "status": "in_progress", "startedAt": "started"},
            {"id": "publish", "status": "pending"},
        ],
        "financial_report_context": comparison_report(),
    }
    tasks = interrupt_financial_progress(state)
    assert tasks[0] == {"id": "read", "status": "completed", "finishedAt": "saved"}
    assert tasks[1]["status"] == "error" and tasks[1]["startedAt"] == "started"
    assert tasks[1]["finishedAt"] and "草稿已保留" in tasks[1]["detail"]
    assert tasks[2]["status"] == "pending"
    assert state["financial_report_context"]["workflow"]["status"] == "draft"
