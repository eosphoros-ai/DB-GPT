"""Stable public stages, independent of internal tasks, retries and tool calls."""

from datetime import datetime, timezone

STAGES = ("读取财报", "分析财务数据", "核对结论", "生成报告")
IDS = ("read", "analyze", "review", "publish")
TERMINAL = {"ready", "reviewed", "insufficient", "failed"}


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
        details[1] = f"已保存 {len(report.get('findings', []))} 条通过校验的分析发现。"
        topics = flow.get("topics", [])
        if topics and all(t["status"] in TERMINAL for t in topics):
            current = 2
            details[2] = "正在核对结论与数据的对应关系、期间口径和解释依据。"
        if flow.get("review") and all(
            t["status"] in {"reviewed", "insufficient", "failed"} for t in topics
        ):
            current = 3
            details[2] = "已完成结论核对。"
            details[3] = "正在汇总有依据的内容，生成可查看和下载的报告。"
        if flow.get("status") == "published":
            current = 4
            details[3] = "报告已生成，可查看分析内容、原文依据和下载文件。"
    elif stage in {"calculate", "save"}:
        details[0] = "已读取 PDF，正在核对财务数据、计算指标并保存原文依据。"

    if current == 1:
        activity = activity or {}
        messages = []
        if activity.get("generating"):
            messages.append("正在并行生成分析，等待模型返回")
        if activity.get("validating"):
            messages.append("正在校验数字、计算引用和原文依据")
        if activity.get("repairing"):
            messages.append("正在补充和修正分析表述")
        details[1] += "；".join(messages) + "。" if messages else "正在分析财务数据。"
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
