"""Keep the financial agent on its persisted workflow and bound stalled turns."""

import asyncio
import copy
import json
import time

from dbgpt.agent import ActionOutput
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.util.react_parser import extract_terminate_output
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.json_utils import parse_or_raise_error
from dbgpt_serve.financial_analysis.summary import is_published, report_summary
from dbgpt_serve.financial_analysis.workflow import next_action

from .tools.financial_tools import (
    _result,
    financial_answer_error,
    financial_execution_guidance,
)

FINANCIAL_COMPLETION_MAX_ATTEMPTS = 3
FINANCIAL_COMPLETION_TIMEOUT = 45


class FinancialWorkflowAgent(ToolCallingReActAgent):
    """Restrict active report work to the next persisted transition."""

    def _financial_state(self):
        return getattr(self, "_report_repair_state", None) or {}

    def _completion_phase(self):
        state = self._financial_state()
        phase = state.get("_financial_completion")
        report = state.get("financial_report_context") or {}
        if (
            phase
            and is_published(report)
            and phase["run_id"] == report["report"]["run"]["id"]
            and phase["revision"] == report["revision"]
        ):
            return phase
        return None

    def _completion_remaining(self, phase):
        return FINANCIAL_COMPLETION_TIMEOUT - (time.monotonic() - phase["started"])

    def _completion_fallback(self, reason):
        state = self._financial_state()
        phase = self._completion_phase()
        # Only a persisted publication can reach this path. Never promote a draft.
        content = json.dumps(
            {"output": report_summary(state["financial_report_context"])},
            ensure_ascii=False,
        )
        phase.update(fallback_reason=reason, fallback_output=content)
        object.__setattr__(self, "_pending_native_tool_calls", None)
        return ActionOutput(
            is_exe_success=True,
            terminate=True,
            have_retry=False,
            action="terminate",
            action_input=content,
            content=content,
        )

    def _pending_report(self):
        state = self._financial_state()
        report = state.get("financial_report_context") or {}
        if report.get("workflow", {}).get("status") == "draft" and report.get(
            "report", {}
        ).get("run", {}).get("id") in state.get("financial_pending", ()):
            return report
        return None

    def _build_native_tools(self):
        tools = super()._build_native_tools()
        if self._completion_phase():
            return [t for t in tools if t["function"]["name"] == "terminate"]
        report = self._pending_report()
        if not report:
            return tools
        expected = next_action(report)
        allowed = {expected["tool"], "read_financial_report"}
        if expected["tool"] == "save_financial_topic":
            allowed.add("get_financial_topic")
        return [t for t in tools if t["function"]["name"] in allowed]

    def _native_tool_choice(self):
        return (
            "required"
            if self._pending_report() or self._completion_phase()
            else super()._native_tool_choice()
        )

    async def thinking(self, messages, sender=None, prompt=None, stream_callback=None):
        phase = self._completion_phase()
        guidance = (
            financial_execution_guidance(self._financial_state())
            if self._pending_report()
            else ""
        )
        if phase:
            guidance = (
                "\n本轮财报已发布，数据与结论已保存在返回的 "
                "completion_context 中。现在只调用 terminate，"
                "output 按 completion_instructions 撰写；"
                "不得再次读取、准备、复核、发布报告或启动其他工具。"
                "收到最终回答校验反馈时，仅修正 output 中的问题。"
                "使用完整工具调用参数，不要在工具调用之外直接输出正文。"
            )
        if guidance:
            messages = copy.deepcopy(messages)
            if messages and messages[0].role == "system":
                messages[0].content = (messages[0].content or "") + guidance
            else:
                prompt = (prompt or "") + guidance
        if phase and (
            phase.get("fallback_reason")
            or phase["attempts"] >= FINANCIAL_COMPLETION_MAX_ATTEMPTS
            or self._completion_remaining(phase) <= 0
        ):
            phase.setdefault("fallback_reason", "completion_budget")
            return "", None
        thinking = super().thinking(
            messages, sender=sender, prompt=prompt, stream_callback=stream_callback
        )
        if not phase:
            return await thinking
        try:
            return await asyncio.wait_for(
                thinking, timeout=self._completion_remaining(phase)
            )
        except (asyncio.TimeoutError, LLMChatError) as exc:
            phase["fallback_reason"] = type(exc).__name__
            object.__setattr__(self, "_pending_native_tool_calls", None)
            return "", None

    async def correctness_check(self, message):
        output = message.action_report
        if (
            output
            and output.terminate
            and is_published(
                self._financial_state().get("financial_report_context") or {}
            )
        ):
            phase = self._completion_phase()
            # The fallback is already rendered from retained, validated findings.
            # Only that exact output for the pinned publication bypasses re-rendering.
            if not phase or phase.get("fallback_output") != output.content:
                try:
                    content = extract_terminate_output(output.content or "")
                except ValueError as exc:
                    return False, str(exc)
                error = financial_answer_error(
                    content,
                    self._financial_state(),
                    repair_limit=None if phase else 2,
                )
                if error:
                    return False, error
        return await super().correctness_check(message)

    async def verify(self, message, sender, reviewer=None, **kwargs):
        valid, reason = await super().verify(message, sender, reviewer, **kwargs)
        phase = self._completion_phase()
        if (
            not valid
            and phase
            and (
                phase["attempts"] >= FINANCIAL_COMPLETION_MAX_ATTEMPTS
                or self._completion_remaining(phase) <= 0
            )
        ):
            fallback = self._completion_fallback("completion_budget")
            # generate_reply also retains this ActionOutput locally. Update the
            # same object so its termination check observes the safe fallback.
            for name, value in fallback.to_dict().items():
                setattr(message.action_report, name, value)
            return await super().verify(message, sender, reviewer, **kwargs)
        return valid, reason

    def _requested_calls(self, message, kwargs):
        native = kwargs.get("tool_calls") or getattr(
            self, "_pending_native_tool_calls", None
        )
        if native:
            raw = [
                (
                    call.get("function", {}).get("name"),
                    call.get("function", {}).get("arguments", "{}"),
                )
                for call in native
            ]
        else:
            try:
                raw = [
                    (s.action, s.action_input)
                    for s in self.parser.parse(message.content or "")
                ]
            except ValueError:
                return []
        calls = []
        for name, arguments in raw:
            try:
                args = (
                    parse_or_raise_error(arguments)
                    if isinstance(arguments, str)
                    else arguments
                )
            except (ValueError, TypeError):
                args = {}
            # Keep the tool name so malformed arguments cannot bypass the
            # workflow gate. The protocol validator still checks legal calls.
            if not isinstance(args, dict):
                args = {}
            if name:
                calls.append((name, args))
        return calls

    def _workflow_feedback(self, report, reason):
        payload = json.loads(_result(report, self._financial_state()["conv_id"]))
        payload.update(success=False, error_code="FINANCIAL_WORKFLOW_BLOCKED")
        payload["message"] = reason
        payload["chunks"] = [{"output_type": "text", "content": reason}]
        return json.dumps(payload, ensure_ascii=False)

    async def act(self, message, sender, **kwargs):
        state = self._financial_state()
        saved = state.get("financial_report_context") or {}
        calls = self._requested_calls(message, kwargs)
        phase = self._completion_phase()
        if phase:
            phase["attempts"] += 1
            if (
                phase.get("fallback_reason")
                or phase["attempts"] > FINANCIAL_COMPLETION_MAX_ATTEMPTS
                or self._completion_remaining(phase) <= 0
            ):
                return self._completion_fallback(
                    phase.get("fallback_reason") or "completion_timeout"
                )
            if len(calls) != 1 or calls[0][0] != "terminate":
                if phase["attempts"] >= FINANCIAL_COMPLETION_MAX_ATTEMPTS:
                    return self._completion_fallback("completion_budget")
                return ActionOutput(
                    is_exe_success=False,
                    content=(
                        "FINANCIAL_COMPLETION_ONLY: 报告已发布。"
                        "本次调用未执行；只调用 terminate，"
                        "用已返回的 completion_context 完成 output，"
                        "无需再次读取、准备或复核报告。"
                    ),
                )
            output = await super().act(message, sender, **kwargs)
            if not output.is_exe_success and (
                phase["attempts"] >= FINANCIAL_COMPLETION_MAX_ATTEMPTS
                or not output.have_retry
            ):
                return self._completion_fallback("completion_budget")
            return output
        if saved.get("workflow", {}).get("status") == "draft" and any(
            name
            in {
                "save_financial_topic",
                "review_financial_report",
                "publish_financial_report",
            }
            for name, args in calls
        ):
            state.setdefault("financial_pending", set()).add(
                saved["report"]["run"]["id"]
            )
        before = self._pending_report()
        revision = before["revision"] if before else None
        output = None
        if before:
            expected = next_action(before)
            for name, args in calls:
                legal = name == expected["tool"] and (
                    "topic_id" not in expected["arguments"]
                    or args.get("topic_id") == expected["arguments"]["topic_id"]
                )
                legal = legal or name == "read_financial_report"
                legal = legal or (
                    name == "get_financial_topic"
                    and expected["tool"] == "save_financial_topic"
                    and args.get("topic_id") == expected["arguments"]["topic_id"]
                )
                legal = (
                    legal
                    and (
                        not args.get("run_id")
                        or args["run_id"] == before["report"]["run"]["id"]
                    )
                    and not args.get("retry")
                )
                if name == "read_financial_report" and args.get("revision"):
                    legal = legal and args["revision"] == revision
                if not legal or len(calls) != 1:
                    output = ActionOutput(
                        is_exe_success=False,
                        action=name,
                        action_input=json.dumps(args, ensure_ascii=False),
                        content=self._workflow_feedback(
                            before,
                            "本次调用未执行：当前版本必须先完成指定步骤。"
                            "请执行返回的 next_action；"
                            "不要重复复核、重开失败专题或读取无关专题。",
                        ),
                    )
                    break
        if output is None:
            output = await super().act(message, sender, **kwargs)
        if output.is_exe_success and any(
            name
            in {"sql_query", "chart_query", "knowledge_retrieve", "semantic_search"}
            or name.startswith("kb_")
            for name, _ in calls
        ):
            state["financial_other_source_used"] = True
        if not output.is_exe_success and "REVIEW_REPAIR_EXHAUSTED" in (
            output.content or ""
        ):
            output.have_retry = False
            output.content = (
                "FINANCIAL_NO_PROGRESS: 已达到本次自动复核修订上限，"
                "草稿和有效数据已保留；尚未发布。"
            )
            output.observations = output.content
        after = self._pending_report()
        if before and after and revision == after["revision"]:
            # Reads and rejected calls do not advance the report. Count them
            # together, including apparently successful repeated reads.
            state["_financial_stalled_calls"] = (
                state.get("_financial_stalled_calls", 0) + 1
            )
            if state["_financial_stalled_calls"] >= 3 and output.have_retry:
                output.is_exe_success = False
                output.have_retry = False
                output.terminate = False
                output.content = (
                    "FINANCIAL_NO_PROGRESS: "
                    "连续三次调用未推进当前财报，已停止自动重试。"
                    "财务数据和草稿已保留，未完成的修订与复核不会自动通过。"
                )
                output.observations = output.content
            elif not output.is_exe_success and output.have_retry:
                if "FINANCIAL_WORKFLOW_BLOCKED" not in (output.content or ""):
                    output.content = self._workflow_feedback(after, output.content)
                    output.observations = output.content
        else:
            state["_financial_stalled_calls"] = 0
        report = state.get("financial_report_context") or {}
        if (
            output.is_exe_success
            and is_published(report)
            and any(
                name
                in {
                    "prepare_financial_report",
                    "prepare_financial_comparison",
                    "review_financial_report",
                    "publish_financial_report",
                }
                for name, _ in calls
            )
        ):
            state["_financial_completion"] = {
                "run_id": report["report"]["run"]["id"],
                "revision": report["revision"],
                "started": time.monotonic(),
                "attempts": 0,
            }
            state.pop("financial_answer_repairs", None)
        return output
