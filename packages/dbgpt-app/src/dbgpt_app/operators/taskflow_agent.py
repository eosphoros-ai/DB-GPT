"""TaskFlow agent node operator.

``TFAgentOperator`` runs one focused ReAct agent task (via
:mod:`dbgpt_app.operators.agent_runner`) as a product node in a TaskFlow DAG.

Live progress: every ReAct round rebuilds a ``vis-flow-step`` marker with
``status: "running"`` plus the accumulated trace (thinking / tool / observation)
and pushes it to the per-chat step-event queue — the chat UI dedupes by
step_id (keep-last), so the node card shows a live, self-updating ReAct trace
instead of a static spinner. The final ``status: success`` marker is produced
by the regular ``TFStepMarkerOperator`` downstream, so the stored final text
stays identical to other nodes.
"""

import logging
from typing import List, Optional

from dbgpt._private.config import Config
from dbgpt.core import LLMClient
from dbgpt.core.awel import JoinOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    Parameter,
    ViewMetadata,
)
from dbgpt.model.operators import MixinLLMOperator
from dbgpt.util.i18n_utils import _

from .agent_runner import AgentStepEvent, run_react_agent
from .taskflow import (
    SHARE_KEY_TASKFLOW_CONV_UID,
    build_step_marker,
    get_step_event_queue,
    strip_step_markers,
)

logger = logging.getLogger(__name__)

CFG = Config()

#: Max trace lines kept in the live payload (older rounds are collapsed).
_MAX_TRACE_LINES = 24

_KIND_ICON = {"thinking": "💭", "action": "🔧", "observation": "👁", "answer": "✅"}


def _list_param(label: str, name: str, desc: str) -> Parameter:
    return Parameter.build_from(
        _(label),
        name,
        str,
        is_list=True,
        optional=True,
        default=None,
        description=_(desc),
    )


class TFAgentOperator(MixinLLMOperator, JoinOperator[str]):
    """Run a scoped ReAct agent as one TaskFlow node."""

    metadata = ViewMetadata(
        label=_("TaskFlow Agent Operator"),
        name="taskflow_agent_operator",
        description=_("Run a scoped ReAct agent as one TaskFlow node."),
        category=OperatorCategory.LLM,
        parameters=[
            Parameter.build_from(
                _("Agent Profile"),
                "agent_profile",
                str,
                optional=True,
                default="react_general",
                description=_("The builtin agent profile id."),
            ),
            Parameter.build_from(
                _("Goal"),
                "goal",
                str,
                description=_("The node objective prompt."),
            ),
            Parameter.build_from(
                _("Model"),
                "model",
                str,
                optional=True,
                default=None,
                description=_("The LLM model name (default: chat model)."),
            ),
            _list_param("Tools", "tools", "Selected builtin tool ids."),
            _list_param("Skills", "skills", "Selected skill package names."),
            _list_param("Datasources", "datasources", "Selected datasource names."),
            _list_param("Knowledge", "knowledge", "Selected knowledge space ids."),
            _list_param("MCP", "mcp", "Inline MCP specs (sse:/http: + url)."),
            Parameter.build_from(
                _("Max Turns"),
                "max_turns",
                int,
                optional=True,
                default=10,
                description=_("ReAct loop cap."),
            ),
            Parameter.build_from(
                _("Step ID"),
                "step_id",
                str,
                optional=True,
                default=None,
                description=_("The TaskFlow DSL node id (for live events)."),
            ),
            Parameter.build_from(
                _("Step Label"),
                "step_label",
                str,
                optional=True,
                default=None,
                description=_("The node label (for live events)."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("User question"),
                "query",
                str,
                description=_("The end-user's original question."),
            ),
            IOField.build_from(
                _("Upstream data"),
                "upstream_data",
                str,
                description=_("Clean outputs of all prior nodes."),
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Agent answer"),
                "answer",
                str,
                description=_("The agent's final answer."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        goal: str,
        agent_profile: Optional[str] = "react_general",
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        tools: Optional[List[str]] = None,
        skills: Optional[List[str]] = None,
        datasources: Optional[List[str]] = None,
        knowledge: Optional[List[str]] = None,
        mcp: Optional[List[str]] = None,
        max_turns: int = 10,
        step_id: Optional[str] = None,
        step_label: Optional[str] = None,
        **kwargs,
    ):
        JoinOperator.__init__(self, combine_function=self._join_func, **kwargs)
        MixinLLMOperator.__init__(self, llm_client=llm_client, **kwargs)
        self._goal = goal
        self._agent_profile = agent_profile
        self._model = model
        self._tools = tools
        self._skills = skills
        self._datasources = datasources
        self._knowledge = knowledge
        self._mcp = mcp
        self._max_turns = max_turns
        self._step_id = step_id
        self._step_label = step_label

    async def _join_func(self, question: str, *args) -> str:
        data_parts = [strip_step_markers(a) for a in args if isinstance(a, str) and a]
        upstream_sections = [
            ("上游节点", "data", part) for part in data_parts if part.strip()
        ]

        zh = True
        try:
            if self.system_app:
                zh = self.system_app.config.get_current_lang() == "zh"
        except Exception:
            pass

        trace_lines: List[str] = []
        trace_events: List[AgentStepEvent] = []
        queue = None
        try:
            conv_uid = await self.current_dag_context.get_from_share_data(
                SHARE_KEY_TASKFLOW_CONV_UID
            )
            queue = get_step_event_queue(conv_uid)
        except Exception:
            queue = None

        async def _push_live() -> None:
            if queue is None or not self._step_id:
                return
            visible = trace_lines[-_MAX_TRACE_LINES:]
            hidden = len(trace_lines) - len(visible)
            body = "\n".join(visible)
            if hidden > 0:
                body = f"…(前面 {hidden} 步已折叠)\n" + body
            steps = [
                {
                    "kind": e.kind,
                    "title": e.title,
                    "detail": (e.detail or "").strip().replace("\n", " ")[:240],
                    "round": e.round,
                }
                for e in trace_events[-12:]
            ]
            marker = build_step_marker(
                step_id=self._step_id,
                label=self._step_label or self._step_id,
                kind="agent",
                status="running",
                summary=None,
                steps=steps,
            )
            try:
                queue.put_nowait(marker + body)
            except Exception:
                pass

        async def _on_step(event: AgentStepEvent) -> None:
            icon = _KIND_ICON.get(event.kind, "•")
            label = event.title
            detail = (event.detail or "").strip().replace("\n", " ")
            line = f"{icon} **{label}**" + (f" {detail[:200]}" if detail else "")
            trace_lines.append(line)
            if event.kind != "answer":
                trace_events.append(event)
            await _push_live()

        answer = await run_react_agent(
            goal=self._goal,
            question=question,
            upstream_sections=upstream_sections,
            profile_id=self._agent_profile,
            tools=self._tools,
            skills=self._skills,
            datasources=self._datasources,
            knowledge=self._knowledge,
            mcp=self._mcp,
            model=self._model,
            max_turns=self._max_turns,
            llm_client=self.llm_client,
            system_app=self.system_app,
            on_step=_on_step,
            language="zh" if zh else "en",
        )
        # Final live frame: full trace + answer before the marker operator
        # emits the canonical success event.
        await _push_live()
        return answer
