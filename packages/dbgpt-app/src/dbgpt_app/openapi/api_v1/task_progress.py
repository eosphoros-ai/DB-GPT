"""Reconcile delivery tasks from confirmed outcomes, never from termination alone."""

import re
from typing import Any, Dict, List


def complete_delivery_task(
    tasks: List[Dict[str, Any]],
    *,
    report_completed: bool = False,
    summary_delivered: bool = False,
) -> bool:
    """Complete only the active delivery task; leave unrelated work untouched."""
    active = next(
        (i for i, task in enumerate(tasks) if task.get("status") == "in_progress"),
        None,
    )
    if active is None:
        return False
    content = str(tasks[active].get("content", "")).strip().lower()
    report_task = bool(
        re.search(
            r"generate_report|生成.*(?:报告|报表)|(?:generate|render|compose).*report",
            content,
        )
        or re.fullmatch(r"提交(?:最终)?(?:报告|报表)[。.!！\s]*", content)
    )
    summary_task = bool(
        re.fullmatch(
            r"(?:返回|输出|提供|提交)(?:最终)?(?:摘要|总结|回复)[。.!！\s]*|"
            r"(?:return|provide|deliver|output) (?:the )?(?:final )?"
            r"(?:summary|response)[.!\s]*",
            content,
        )
    )
    if not ((report_completed and report_task) or (summary_delivered and summary_task)):
        return False
    tasks[active]["status"] = "completed"
    for task in tasks[active + 1 :]:
        if task.get("status") == "pending":
            task["status"] = "in_progress"
            break
    return True


def task_plan_meta(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use the same denominator as the task card (cancelled tasks excluded)."""
    active = [task for task in tasks if task.get("status") != "cancelled"]
    done = sum(task.get("status") == "completed" for task in active)
    total = len(active)
    state = "done" if total and done == total else "progress" if done else "init"
    return {"state": state, "done": done, "total": total}


def sync_task_plan_steps(
    steps: List[Dict[str, Any]], tasks: List[Dict[str, Any]]
) -> None:
    """The plan card and its timeline label are projections of one task list."""
    meta = task_plan_meta(tasks)
    for step in steps:
        if str(step.get("action", "")).lower() == "todowrite":
            step["todo_meta"] = dict(meta)
            step["title"] = f"TODO::{meta['state']}:{meta['done']}/{meta['total']}"
