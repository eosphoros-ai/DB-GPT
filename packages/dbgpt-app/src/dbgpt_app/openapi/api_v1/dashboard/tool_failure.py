"""Separate failed tool execution from business clarification for one agent turn."""

import json

from dbgpt.agent import ActionOutput

TOOL_STAGES = {
    "propose_dashboard_change": "生成批注修改提案",
    "question": "校验业务追问参数",
    "sql_query": "探索源数据",
    "plan_dashboard": "生成看板规划",
    "load_dashboard_draft": "加载已保存看板",
    "resolve_dashboard_reference": "定位看板组件",
    "create_dashboard_draft": "生成组件查询",
    "repair_dashboard_draft": "修复组件查询",
    "modify_dashboard_draft": "修改看板",
    "revise_dashboard_plan": "修改看板规划",
}


def discovery_correction(state, output):
    """Keep a bounded SQL authoring error in the loop with its real evidence."""
    if (
        output is None
        or output.is_exe_success
        or set((output.action or "").split(", ")) != {"sql_query"}
        or state.get("dashboard_generation")
    ):
        return None
    try:
        payload = json.loads(output.observations or output.content or "{}")
        if isinstance(payload, list):
            # run_tools_batch stores structured per-call observations. Its
            # content is joined JSON documents and cannot be parsed as one.
            if not payload or any(
                not isinstance(item, dict) or item.get("name") != "sql_query"
                for item in payload
            ):
                return None
            failures = [
                json.loads(item.get("observation") or item.get("content") or "{}")
                for item in payload
                if item.get("success") is False
            ]
        else:
            failures = [payload]
    except (TypeError, ValueError):
        return None
    if not failures:
        return None
    for failure in failures:
        if (
            not isinstance(failure, dict)
            or failure.get("error_code") != "SQL_QUERY_FAILED"
        ):
            return None
        reason = "\n".join(
            str(chunk.get("content", ""))
            for chunk in failure.get("chunks", [])
            if isinstance(chunk, dict) and chunk.get("output_type") == "text"
        )
        if not any(
            marker in reason.lower()
            for marker in ("no such table:", "no such column:", "syntax error")
        ):
            # Never recover a batch containing timeout, approval rejection,
            # security failure or an unknown execution error.
            return None
    attempts = state.get("_dashboard_discovery_corrections", 0)
    if attempts >= 2:
        return None
    state["_dashboard_discovery_corrections"] = attempts + 1
    return (
        f"{output.content}\n"
        "The failed discovery SELECTs returned no valid data. "
        "Retain any successful results in this batch; correct failed calls only. "
        "Use the authorized tables, columns and SQL dialect already provided "
        "in the database context. SQLite has no information_schema or pg_catalog. "
        "Do not repeat the failed SQL or ask the user a technical question. "
        "Call sql_query with a corrected SELECT against the listed business "
        "tables, or plan_dashboard from the observations already collected. "
        f"Correction {attempts + 1} of 2; the discovery call limit is unchanged."
    )


def capture_tool_failure(state, output):
    """Use actual execution status / explicit error metadata, never prose guessing."""
    if output is None:
        return None
    try:
        payload = json.loads(output.content or "{}")
    except (TypeError, ValueError):
        payload = {}
    error = (
        payload.get("__dashboard_tool_error__") if isinstance(payload, dict) else None
    )
    if not isinstance(error, dict):
        if output.is_exe_success:
            return None
        error = {
            "tool": output.action or "agent_output",
            "reason": output.content or "工具未返回有效结果。",
            "code": "tool_execution_failed",
        }
    name = error.get("tool") or output.action or "agent_output"
    names = set(name.split(", "))
    stage_name = next(iter(names)) if len(names) == 1 else name
    stage_label = TOOL_STAGES.get(stage_name, "解析或执行模型工具调用")
    reason = str(error.get("reason") or "工具未返回有效结果。")[:2000]
    retry_hint = (
        "本轮已停止，不会要求你解答内部技术问题。"
        "已保存的看板和发布版本保持不变。请检查需求后重新发起本次操作；"
        "如再次失败，请将上述工具名称和错误详情交给维护者排查。"
    )
    generation = state.get("dashboard_generation") or {}
    failure = {
        **generation,
        "type": "dashboard.generation.failed",
        "title": "看板操作失败",
        "reason": error.get("code", "tool_execution_failed"),
        "tool": name,
        "stage": error.get("stage", name),
        "stage_label": stage_label,
        "summary": f"{stage_label}失败：{reason}",
        "message": (
            f"停在「{stage_label}」（{name}）。\n失败原因：{reason}\n{retry_hint}"
        ),
        "retry_hint": retry_hint,
        "source_turn_id": generation.get("source_turn_id") or state.get("conv_id"),
    }
    if generation.get("dashboard_id"):
        failure["editor_path"] = f"/dashboards/{generation['dashboard_id']}"
    state["dashboard_tool_failure"] = failure
    return failure


def failed_action(failure, action=None):
    # LOOP verification checks have_retry, not terminate, on unsuccessful actions.
    return ActionOutput(
        is_exe_success=False,
        have_retry=False,
        terminate=False,
        action=action or failure.get("tool"),
        content=failure["message"],
        observations=failure["message"],
    )
