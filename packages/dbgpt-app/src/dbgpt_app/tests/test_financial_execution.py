import json

from dbgpt_app.openapi.api_v1.financial_execution import FinancialExecutionStream
from dbgpt_serve.financial_analysis.progress import public_progress


def test_streamed_output_is_retained_on_the_same_tool_in_durable_history():
    history = []
    execution = FinancialExecutionStream(history)
    first = execution.start(1, "step-1", "prepare_financial_report", {}, "开始提取")
    tasks = public_progress(stage="extract")
    progress = execution.progress(1, tasks, ["已读取财务科目：营业收入、净利润。"])
    assert first[0]["type"] == "step.chunk"
    assert all(chunk["id"] == "step-1" for chunk in first + progress)
    assert execution.progress(1, tasks) == []  # Same snapshot adds no noise.
    final, was_live = execution.finish(
        1,
        {
            "id": "step-1",
            "title": "prepare_financial_report",
            "status": "running",
            "outputs": [
                {"output_type": "html", "content": {"kind": "financial-report"}}
            ],
        },
    )
    final["status"] = "done"
    assert was_live and len(history) == 1
    assert final is history[0]
    assert final["outputs"][:-1] == [
        {"output_type": c["output_type"], "content": c["content"]}
        for c in first + progress
    ]
    assert json.loads(json.dumps(history)) == history
    assert execution.progress(1, tasks) == []
    assert execution.waiting() == []


def test_waiting_feedback_is_bounded_and_stops_after_completion():
    clock = [0]
    history = []
    execution = FinancialExecutionStream(history, clock=lambda: clock[0])
    execution.start(2, "step-2", "review_financial_report", {}, "正在核对")
    clock[0] = 19
    assert execution.waiting() == []
    clock[0] = 20
    waiting = execution.waiting()
    assert len(waiting) == 1 and "[00:20]" in waiting[0]["content"]
    assert "仍在等待" in waiting[0]["content"]
    assert execution.waiting() == []
    execution.finish(2, {"status": "done"})
    clock[0] = 200
    assert execution.waiting() == []
    assert history[0]["outputs"][-1]["content"] == waiting[0]["content"]


def test_step_switch_failure_and_normal_tools_do_not_mix_execution_outputs():
    history = []
    execution = FinancialExecutionStream(history)
    execution.start(1, "prepare", "prepare_financial_report", {}, "提取中")
    first, _ = execution.finish(1, {"status": "done"})
    execution.start(3, "review", "review_financial_report", {"run_id": "run"}, "复核中")
    execution.progress(3, public_progress(stage="extract"))
    assert "复核中" not in str(first["outputs"])
    assert execution.progress(999, public_progress(stage="save")) == []
    failures = execution.fail_unfinished()
    assert failures == [{"type": "step.done", "id": "review", "status": "failed"}]
    assert history[0]["status"] == "done" and history[1]["status"] == "failed"
    assert "复核中" in str(history[1]["outputs"])
    assert execution.fail_unfinished() == []
    normal = {"id": "sql", "action": "sql_query", "outputs": []}
    assert execution.finish(4, normal) == (normal, False)
    assert len(history) == 2
