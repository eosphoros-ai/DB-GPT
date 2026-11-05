"""Delivery progress must agree in live SSE and persisted history."""

import json
from unittest.mock import MagicMock

import pytest

from dbgpt_app.openapi.api_v1.task_progress import (
    complete_delivery_task,
    task_plan_meta,
)


def task(content, status="in_progress"):
    return {"content": content, "status": status, "priority": "high"}


@pytest.mark.parametrize(
    "warnings,completed",
    [
        ([], True),
        (["REPORT_REFERENCE_UNAVAILABLE: table omitted"], False),
        (["REPORT_NUMERIC_VALUE_UNAVAILABLE: metric omitted"], False),
        (["optional chart annotation"], True),
    ],
)
def test_report_progress_uses_semantic_outcome_before_transport(warnings, completed):
    from dbgpt_app.openapi.api_v1.subagent.report_agent import (
        _completed_report_response,
    )

    state = {
        "_report_presentation": {"content": "<html>Report</html>", "title": "Report"},
        "_report_warnings": warnings,
        "_report_delivery_completed": not completed,
    }
    response = json.loads(_completed_report_response(state))
    assert state["_report_delivery_completed"] is completed
    assert response["status"] == ("completed" if completed else "partial")


@pytest.mark.parametrize("prefix", [2, 5])
def test_report_then_summary_completes_only_confirmed_delivery(prefix):
    tasks = [task("已执行分析", "completed") for _ in range(prefix)]
    tasks += [task("调用 generate_report 生成交互式网页报告")]
    if prefix == 5:
        tasks += [task("返回最终摘要", "pending")]
    assert complete_delivery_task(tasks, report_completed=True)
    assert task_plan_meta(tasks)["done"] == prefix + 1
    if prefix == 5:
        assert tasks[-1]["status"] == "in_progress"
        assert complete_delivery_task(tasks, summary_delivered=True)
    assert task_plan_meta(tasks)["state"] == "done"


@pytest.mark.parametrize(
    "content", ["提交最终报告", "提交报告", "提交最终报表", "提交最终报告。"]
)
def test_report_submission_requires_confirmed_report_delivery(content):
    tasks = [task(content), task("返回最终摘要", "pending")]
    assert not complete_delivery_task(tasks)
    assert not complete_delivery_task(tasks, summary_delivered=True)
    assert tasks[0]["status"] == "in_progress"
    assert complete_delivery_task(tasks, report_completed=True)
    assert tasks[0]["status"] == "completed"
    assert tasks[1]["status"] == "in_progress"


@pytest.mark.parametrize(
    "content",
    [
        "准备提交最终报告",
        "检查提交最终报告所需数据",
        "提交最终报告前核验数据",
        "计算并提交最终报告",
        "编写最终报告",
        "提交最终报告的准备工作",
    ],
)
def test_report_delivery_does_not_complete_submission_preparation(content):
    tasks = [task(content)]
    assert not complete_delivery_task(
        tasks, report_completed=True, summary_delivered=True
    )
    assert tasks[0]["status"] == "in_progress"


@pytest.mark.parametrize(
    "content", ["继续数据分析", "计算并返回最终摘要", "验证报告数字", "检查数据质量"]
)
def test_termination_or_report_does_not_complete_unrelated_work(content):
    tasks = [task(content), task("生成网页报告", "pending")]
    assert not complete_delivery_task(
        tasks, report_completed=True, summary_delivered=True
    )
    assert [t["status"] for t in tasks] == ["in_progress", "pending"]


def test_no_active_task_and_cancelled_tasks_are_preserved():
    tasks = [task("取消的分析", "cancelled"), task("返回最终摘要", "pending")]
    assert not complete_delivery_task(tasks, summary_delivered=True)
    assert task_plan_meta(tasks) == {"state": "init", "done": 0, "total": 1}


def test_pending_analysis_after_report_remains_incomplete():
    tasks = [task("生成网页报告"), task("运行额外分析", "pending")]
    assert complete_delivery_task(tasks, report_completed=True)
    assert not complete_delivery_task(tasks, summary_delivered=True)
    assert tasks[-1]["status"] == "in_progress"


@pytest.mark.parametrize("report_task", ["生成网页报告", "提交最终报告"])
def test_terminal_sse_and_persisted_plan_and_timeline_are_identical(report_task):
    from dbgpt_app.openapi.api_v1 import agentic_data_api as api
    from dbgpt_app.openapi.api_v1.react_final import AgentFinalAnswer

    tasks = [task(report_task), task("取消的任务", "cancelled")]
    assert complete_delivery_task(tasks, report_completed=True)
    history = api._build_react_history_payload(
        final_content="报告已生成",
        task_plan=tasks,
        steps=[{"id": "plan", "action": "todowrite", "title": "TODO::init:0/2"}],
        generated_images=[],
        sub_agents=[],
        input_files=[],
    )
    storage = MagicMock()
    final, done = api._react_terminal_events(
        storage, history, AgentFinalAnswer("报告已生成")
    )
    stored = json.loads(storage.add_view_message.call_args.args[0])
    event = json.loads(final.removeprefix("data: "))
    assert event["task_plan"] == stored["task_plan"] == tasks
    assert (
        stored["steps"][0]["todo_meta"]
        == event["todo_meta"]
        == {
            "state": "done",
            "done": 1,
            "total": 1,
        }
    )
    assert stored["steps"][0]["title"] == "TODO::done:1/1"
    assert json.loads(done.removeprefix("data: "))["type"] == "done"
