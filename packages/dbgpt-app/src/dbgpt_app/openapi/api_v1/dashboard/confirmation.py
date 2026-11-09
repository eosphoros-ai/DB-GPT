"""Bind a confirmation turn to persisted facts, not the model's final prose."""

import json
import re
from typing import Any, Dict, Optional, Tuple

from dbgpt._private.pydantic import PrivateAttr
from dbgpt.agent import ActionOutput
from dbgpt.agent.expand.react_agent import ReActAgent

from .generation_budget import GenerationBudget, check_generation_deadline
from .tool_failure import capture_tool_failure, failed_action

GENERATION_STAGES = {
    "sql_generation": "模型生成 SQL",
    "contract_validation": "组件结构与字段校验",
    "publication_validation": "公开分享数据绑定校验",
    "widget_validation": "组件 SQL 试运行",
    "repair": "修复组件及其分享绑定",
    "saving": "保存看板草稿",
}


def query_batch_size(state: Dict[str, Any]) -> int:
    """Reduce model round trips without enlarging publication/repair payloads."""
    plan = state.get("dashboard_plan") or {}
    # Filtered widgets also carry frozen publication queries and bindings. Keep
    # those payloads small, and fall back after any truncated JSON response.
    if plan.get("filters") or state.get("dashboard_query_small_batches"):
        return 2
    return 4


def observe_generation_event(state, event_type, payload):
    generation = state.get("dashboard_generation")
    if not generation:
        return
    if event_type == "dashboard.generation.progress":
        generation["stage"] = payload["stage"]
    if event_type.startswith("dashboard.widget."):
        generation["stage"] = "widget_validation"
        widget_id = payload.get("widget_id")
        if widget_id:
            generation.setdefault("widget_states", {})[widget_id] = {
                "dashboard.widget.started": "running",
                "dashboard.widget.validated": "validated",
                "dashboard.widget.failed": "failed",
            }[event_type]


async def run_bounded_generation(state, work):
    if not state.get("dashboard_generation"):
        return await work()
    budget = state.setdefault("_dashboard_generation_budget", GenerationBudget())
    return await budget.run(work)


def confirmed_revision(prompt: str) -> int:
    """Read the revision already carried by current and historical UI buttons."""
    revisions = re.findall(r"\b(?:expected\s+)?revision\s+(\d+)\b", prompt, re.I)
    if len(revisions) != 1 or int(revisions[0]) < 1:
        raise ValueError("Reopen the saved plan and confirm its explicit revision.")
    return int(revisions[0])


def require_current_confirmation(record: Any, prompt: str, source: str) -> int:
    revision = confirmed_revision(prompt)
    if len(re.findall(r"\[\[confirm-dashboard:", prompt)) != 1:
        raise ValueError("Confirm exactly one saved plan per turn.")
    if revision != record.current_revision:
        raise ValueError("The plan changed. Reopen it and confirm the new revision.")
    if record.schema_payload.dashboard.data_source_id != source:
        raise ValueError("Select the same data source used by the saved plan.")
    workflow = record.schema_payload.metadata.compatibility.get(
        "agent_dashboard_workflow", {}
    )
    if workflow.get("status") != "awaiting_confirmation":
        raise ValueError("This plan is no longer awaiting confirmation.")
    return revision


def record_generation_result(state: Dict[str, Any], record: Any) -> None:
    generation = state.get("dashboard_generation")
    if not generation or generation["dashboard_id"] != record.id:
        return
    expected = {
        w["widget_id"] for w in state["dashboard_confirmation_contract"]["widgets"]
    }
    actual = {w.id for w in record.schema_payload.widgets}
    failed = [w.id for w in record.schema_payload.widgets if w.error]
    workflow = record.schema_payload.metadata.compatibility.get(
        "agent_dashboard_workflow", {}
    )
    complete = (
        expected == actual
        and not failed
        and record.current_revision > generation["current_revision"]
        and workflow.get("status") == "generated"
    )
    generation.update(
        status="completed" if complete else "repair_required",
        failed_widget_ids=failed,
        saved_widget_ids=[w.id for w in record.schema_payload.widgets if not w.error],
        saved_revision=record.current_revision,
    )


def generation_start_event(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    generation = state.get("dashboard_generation")
    if not generation:
        return None
    budget = state.setdefault("_dashboard_generation_budget", GenerationBudget())
    return {
        **generation,
        "type": "dashboard.generation.started",
        "plan": state["dashboard_plan"],
        "limit_seconds": budget.seconds,
    }


def generation_failure(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if state.get("dashboard_tool_failure"):
        return state["dashboard_tool_failure"]
    generation = state.get("dashboard_generation")
    if not generation or generation.get("status") == "completed":
        return None
    budget = state.get("_dashboard_generation_budget")
    timed_out = budget is not None and budget.stop_reason == "timeout"
    plan = state["dashboard_plan"]
    widgets = plan.get("widgets", [])
    states = generation.get("widget_states", {})
    validated = [w["id"] for w in widgets if states.get(w["id"]) == "validated"]
    failed = [w["id"] for w in widgets if states.get(w["id"]) == "failed"]
    pending = [w["id"] for w in widgets if w["id"] not in validated]
    stage = generation.get("stage", "sql_generation")
    saved_revision = generation.get("saved_revision")
    preservation = (
        f"已保存待修复草稿（修订 {saved_revision}）；本轮未保存的改动未写入。"
        if saved_revision
        else "原规划仍保留；本轮候选 SQL 未保存为可用看板。"
    )
    retry_hint = (
        "请打开保留的规划/草稿检查；可将任务缩小为 3–4 个核心组件，"
        "或明确必要的筛选条件，再确认生成。不会自动重试。"
    )
    reason = f"达到 {budget.seconds} 秒时限" if timed_out else "本轮执行已结束"
    summary = (
        f"本次看板生成未完成：{reason}，"
        f"停在「{GENERATION_STAGES.get(stage, stage)}」。"
        f"{len(validated)}/{len(widgets)} 个组件最近一次 SQL 试运行通过"
        "（不等于已保存）。"
        f"{preservation}"
    )
    titles = {w["id"]: w.get("title", w["id"]) for w in widgets}
    completed_titles = "、".join(titles[item] for item in validated) or "无"
    pending_titles = "、".join(titles[item] for item in pending) or "无"
    message = (
        f"{summary}\n试运行通过：{completed_titles}。"
        f"\n尚未通过试运行：{pending_titles}。\n{retry_hint}"
    )
    return {
        **generation,
        "type": "dashboard.generation.failed",
        "message": message,
        "summary": f"本次看板生成未完成：{reason}。",
        "reason": "timeout" if timed_out else "incomplete",
        "stage": stage,
        "stage_label": GENERATION_STAGES.get(stage, stage),
        "limit_seconds": budget.seconds if budget else None,
        "validated_widget_ids": validated,
        "failed_widget_ids": failed,
        "pending_widget_ids": pending,
        "staged_widget_ids": list(
            (state.get("dashboard_query_staging") or {}).get("widgets", {})
        ),
        "validated_widgets": len(validated),
        "failed_widgets": len(failed),
        "plan": plan,
        "editor_path": f"/dashboards/{generation['dashboard_id']}",
        "retry_hint": retry_hint,
        "revision_prompt": (
            f"[[revise-dashboard-plan:{generation['dashboard_id']}]] Revise this "
            f"dashboard plan at expected revision {generation['current_revision']} "
            "as follows: "
        )
        if not saved_revision
        else None,
    }


def continuation_feedback(state: Dict[str, Any]) -> Optional[str]:
    if generation_failure(state) is None:
        return None
    generation = state["dashboard_generation"]
    if generation.get("status") == "repair_required":
        return (
            "Generation is not complete. Call repair_dashboard_draft for failed "
            "widgets only: " + ", ".join(generation.get("failed_widget_ids", []))
        )
    contract = state["dashboard_confirmation_contract"]
    staged = state.get("dashboard_query_staging") or {}
    present = set((staged.get("widgets") or {}).keys())
    missing = [
        w["widget_id"] for w in contract["widgets"] if w["widget_id"] not in present
    ]
    return (
        "The user already confirmed this plan. Generation is not complete. "
        "Do not ask for confirmation again or finish with prose. "
        "Call create_dashboard_draft with the confirmed dashboard_id and revision, "
        "widget_queries: {widgets: [...]}, at most "
        f"{query_batch_size(state)} missing widgets: "
        + ", ".join(missing)
        + ". Use the previous tool error to correct invalid arguments. "
        "The original step budget is unchanged."
    )


class DashboardConfirmationAgent(ReActAgent):
    """Guard Dashboard failures and keep confirmed generation in its bounded loop."""

    _dashboard_state: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _saved_completion: Optional[Tuple[str, Optional[str]]] = PrivateAttr(default=None)

    def __init__(self, *, dashboard_state: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        # A private reference (not a copied Pydantic field) observes real tool writes.
        self._dashboard_state = dashboard_state

    async def thinking(self, messages, sender=None, prompt=None, stream_callback=None):
        # The tool already persisted the plan/result and emitted its UI card.
        # Finish through the normal terminate action, preserving SSE/history and
        # tool steps, without another model call just to restate saved facts.
        if self._saved_completion is not None:
            summary, model = self._saved_completion
            self._saved_completion = None
            return (
                "Thought: The saved result is ready for review.\n"
                "Action: terminate\nAction Input: "
                + json.dumps({"output": summary}, ensure_ascii=False),
                model,
            )
        return await super().thinking(messages, sender, prompt, stream_callback)

    def _completion_from_saved_result(self, output):
        if not output or not output.is_exe_success:
            return None
        state = self._dashboard_state
        english = state.get("_report_language", "en") == "en"
        if output.action == "plan_dashboard":
            try:
                payload = json.loads(output.content or "{}")
            except (TypeError, ValueError):
                return None
            if not isinstance(payload, dict):
                return None
            reference = payload.get("__dashboard_ref__") or {}
            if (
                reference.get("status") != "awaiting_confirmation"
                or reference.get("dashboard_id") != state.get("dashboard_record_id")
                or reference not in (state.get("dashboard_refs") or [])
            ):
                return None
            plan = reference["plan"]
            title = plan["title"]
            widgets, filters = len(plan["widgets"]), len(plan.get("filters") or [])
            return (
                f'Plan "{title}" saved: {widgets} widgets and {filters} filters. '
                "Review the plan card, then confirm generation or request changes."
                if english
                else f"《{title}》规划已保存：{widgets} 个图表、{filters} 个筛选。"
                "请查看规划卡片，确认生成或提出修改。"
            )
        generation = state.get("dashboard_generation") or {}
        if output.action in {"create_dashboard_draft", "repair_dashboard_draft"} and (
            generation.get("status") == "completed"
        ):
            count = len(generation["saved_widget_ids"])
            return (
                f"Dashboard saved. All {count} widgets passed query validation. "
                "Open the dashboard to review the results."
                if english
                else f"看板已保存，{count} 个图表已通过查询验证。请打开看板查看结果。"
            )
        return None

    async def act(self, message, sender, **kwargs):
        self._saved_completion = None
        check_generation_deadline()
        if self._dashboard_state.get("dashboard_tool_failure"):
            return failed_action(self._dashboard_state["dashboard_tool_failure"])
        feedback = continuation_feedback(self._dashboard_state)
        if feedback:
            try:
                steps = self.parser.parse_current_step(message.content or "")
            except Exception:
                # Preserve the shared parser's existing malformed-output recovery.
                steps = []
            if len(steps) == 1 and str(steps[0].action).lower() not in {
                "load_dashboard_draft",
                "create_dashboard_draft",
                "repair_dashboard_draft",
            }:
                # A phase mistake is not a failed database operation. Do not
                # dispatch forbidden discovery/style tools, which would turn a
                # recoverable model error into a terminal ToolNotFound failure.
                return ActionOutput(
                    is_exe_success=False,
                    have_retry=True,
                    terminate=False,
                    action=steps[0].action,
                    content=(
                        f"{steps[0].action} is unavailable during confirmed "
                        "generation. "
                        "Use the supplied temporal evidence; do not run discovery "
                        "or reload styles. " + feedback
                    ),
                )
        try:
            output = await super().act(message, sender, **kwargs)
        except Exception as exc:
            output = ActionOutput(
                is_exe_success=False,
                content=f"{type(exc).__name__}: {exc}",
                action="agent_output",
            )
        failure = capture_tool_failure(self._dashboard_state, output)
        if failure:
            return failed_action(failure, output.action)
        summary = self._completion_from_saved_result(output)
        if summary:
            self._saved_completion = (summary, message.model_name)
        return output
