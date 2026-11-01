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
    stage_label = TOOL_STAGES.get(name, "解析或执行模型工具调用")
    reason = str(error.get("reason") or "工具未返回有效结果。")[:2000]
    retry_hint = (
        "本轮已停止，不会要求你解答内部技术问题。"
        "已保存的看板和发布版本保持不变。请检查需求后重新发起本次操作；"
        "如再次失败，请将上述工具名称和错误详情交给维护者排查。"
    )
    failure = {
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
        "source_turn_id": state.get("conv_id"),
    }
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
