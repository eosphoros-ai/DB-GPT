"""Stable public stages, independent of internal tasks, retries and tool calls."""

from datetime import datetime, timezone

STAGES = ("读取财报", "分析财务数据", "核对结论", "生成报告")
IDS = ("read", "analyze", "review", "publish")
TERMINAL = {"ready", "reviewed", "insufficient", "failed"}


def analysis_detail(report, activity):
    topics = report.get("workflow", {}).get("topics", [])
    complete = [t["title"] for t in topics if t["status"] in {"ready", "reviewed"}]
    incomplete = [
        t["title"] for t in topics if t["status"] in {"failed", "insufficient"}
    ]
    messages = []
    if complete:
        messages.append("已完成分析：" + "、".join(complete) + "。")
    if incomplete:
        messages.append(
            "尚待补充：" + "、".join(incomplete) + "；已有数据和有效分析已保留。"
        )
    phases = (activity or {}).get("topics", {})
    for phase, label in (
        ("generating", "正在分析"),
        ("validating", "正在核验数据与引用"),
        ("repairing", "正在修正结论与引用"),
    ):
        names = [t["title"] for t in topics if phases.get(t["id"]) == phase]
        if names:
            messages.append(label + "：" + "、".join(names) + "。")
    if not phases and not all(t["status"] in TERMINAL for t in topics):
        names = [
            t["title"] for t in topics if t["status"] in {"running", "needs_revision"}
        ]
        messages.append(
            "正在分析：" + "、".join(names) + "。"
            if names
            else "正在分析经营表现、盈利质量、现金流与资产负债。"
        )
    return "".join(messages) or "正在结合财务数据和原文依据形成分析。"


def public_progress(
    report=None, *, stage=None, previous=(), activity=None, error=False
):
    now = datetime.now(timezone.utc).isoformat()
    current = 0
    details = ["正在读取 PDF，提取财务数据和原文依据。", "", "", ""]
    flow = (report or {}).get("workflow", {})
    if report:
        details[0] = (
            f"已提取 {len(report.get('facts', []))} 项财务数据，"
            f"整理 {len(report.get('calculations', []))} 项指标计算。"
        )
        current = 1
        details[1] = analysis_detail(report, activity)
        topics = flow.get("topics", [])
        if topics and all(t["status"] in TERMINAL for t in topics):
            current = 2
            details[2] = (
                "正在复核已有分析的比较方向、期间口径和原文依据；已有内容可先查看。"
            )
        if flow.get("review") and all(
            t["status"] in {"reviewed", "insufficient", "failed"} for t in topics
        ):
            current = 3
            details[2] = "已完成结论核对。"
            details[3] = "正在汇总有依据的内容，生成可查看和下载的报告。"
        if flow.get("status") == "published":
            current = 4
            incomplete = any(t["status"] in {"failed", "insufficient"} for t in topics)
            details[3] = (
                "报告已生成，未完成的分析已在对应章节说明；可查看已有结论、原文依据和下载文件。"
                if incomplete
                else "报告已生成，可查看分析内容、原文依据和下载文件。"
            )
    elif stage in {"calculate", "save"}:
        details[0] = "已读取 PDF，正在核对财务数据、计算指标并保存原文依据。"

    if error:
        current = min(current, 3)
        details[current] = "本次执行已中断，请稍后重试；已保存的内容仍可查看。"

    old = {t.get("id"): t for t in previous}
    tasks = []
    for index, (key, title) in enumerate(zip(IDS, STAGES)):
        task_id = "financial-" + key
        status = (
            "completed"
            if index < current
            else "error"
            if index == current and error
            else "in_progress"
            if index == current
            else "pending"
        )
        before = old.get(task_id, {})
        task = {
            "id": task_id,
            "kind": "financial-stage",
            "content": title,
            "status": status,
            "priority": "high",
            "detail": details[index],
            "updatedAt": now,
        }
        if status != "pending":
            task["startedAt"] = before.get("startedAt", now)
            if (
                before.get("status") in {"completed", "error"}
                and status == "in_progress"
            ):
                task["startedAt"] = now
            if status in {"completed", "error"}:
                task["finishedAt"] = before.get("finishedAt", now)
        if all(task.get(k) == before.get(k) for k in ("status", "detail")):
            task["updatedAt"] = before.get("updatedAt", now)
        tasks.append(task)
    return tasks
