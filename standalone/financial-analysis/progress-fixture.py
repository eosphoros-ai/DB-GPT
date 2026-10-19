"""Generate public step events with production helpers; no PDF/model/DB access."""

import json
import sys
from pathlib import Path

from dbgpt_app.openapi.api_v1.financial_execution import FinancialExecutionStream
from dbgpt_serve.financial_analysis.progress import public_progress


def build():
    clock = [0]
    history = []
    execution = FinancialExecutionStream(history, clock=lambda: clock[0])
    read = public_progress(stage="extract")
    report = {
        "facts": [{}, {}],
        "calculations": [{}],
        "findings": [],
        "workflow": {"topics": [{"status": "running"}]},
    }
    analyze = public_progress(report, previous=read, activity={"generating": 3})
    report["findings"] = [{}, {}]
    validated = public_progress(report, previous=analyze, activity={"validating": 1})
    report["workflow"]["topics"][0]["status"] = "ready"
    checking = public_progress(report, previous=validated)
    report["workflow"].update(status="published", review={"checked": True})
    published = public_progress(report, previous=checking)
    reading = [
        {
            "type": "step.start",
            "id": "step-1",
            "step": 1,
            "title": "prepare_financial_report",
            "detail": "Action: prepare_financial_report",
        },
        {
            "type": "step.meta",
            "id": "step-1",
            "action": "prepare_financial_report",
            "action_input": {},
            "title": "prepare_financial_report",
        },
        *execution.start(
            1, "step-1", "prepare_financial_report", {}, "开始读取财报和原文依据。"
        ),
        *execution.progress(1, read),
    ]
    clock[0] = 5
    analysis = execution.progress(
        1, analyze, ["已读取财务科目：营业收入、净利润、经营活动现金流。"]
    )
    clock[0] = 26
    waiting = execution.waiting()
    clock[0] = 30
    findings = execution.progress(
        1,
        validated,
        [
            "已校验的分析发现（待最终复核）：收入与利润变化方向一致，具体驱动因素仍需结合附注核对。",
            "已校验的分析发现（待最终复核）：现金流对利润的支撑需要结合经营回款与营运资金变化判断。",
        ],
    )
    clock[0] = 32
    ready = execution.progress(1, checking)
    execution.finish(1, {"status": "done"})
    ready.append({"type": "step.done", "id": "step-1", "status": "done"})
    reviewing = [
        {
            "type": "step.start",
            "id": "step-2",
            "step": 2,
            "title": "review_financial_report",
            "detail": "Action: review_financial_report",
        },
        {
            "type": "step.meta",
            "id": "step-2",
            "action": "review_financial_report",
            "action_input": {"run_id": "preview-report", "revision": "v1"},
            "title": "review_financial_report",
        },
        *execution.start(
            2,
            "step-2",
            "review_financial_report",
            {"run_id": "preview-report", "revision": "v1"},
            "正在核对结论方向、期间口径与解释依据。",
        ),
    ]
    clock[0] = 36
    done = execution.progress(2, published)
    execution.finish(2, {"status": "done"})
    done.append({"type": "step.done", "id": "step-2", "status": "done"})
    return {
        "tasks": {
            "read": read,
            "analysis": analyze,
            "validated": validated,
            "checking": checking,
            "published": published,
        },
        "events": {
            "read": reading,
            "analysis": analysis,
            "waiting": waiting,
            "validated": findings,
            "checking": ready,
            "reviewing": reviewing,
            "published": done,
        },
        "history": history,
    }


if __name__ == "__main__":
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
