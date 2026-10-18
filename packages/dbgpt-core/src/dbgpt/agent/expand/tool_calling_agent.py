"""ReAct agent with hermes-style loop enhancements (opt-in, by flag).

This module adds :class:`ToolCallingReActAgent`, a drop-in subclass of
:class:`~dbgpt.agent.expand.react_agent.ReActAgent` that layers hermes-agent
inspired engineering robustness on top of the existing text ReAct protocol.
All enhancements are gated by ``AgentContext`` flags and default to off, so the
legacy ``ReActAgent`` behaviour (single action per round, coarse fail_reason
feedback) is preserved untouched.

Stage 1 (protocol unchanged):
  - ``enable_parallel_tool_execution``: execute every parsed ReAct step from a
    single model turn concurrently via :func:`run_tools_batch`.
  - ``enable_agent_error_classification``: bucket errors into categories so
    the retry / failover path can react to them instead of one coarse reason.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.agent import (
    ActionOutput,
    Agent,
    AgentMessage,
    ProfileConfig,
)
from dbgpt.agent.resource import BaseTool, ToolPack
from dbgpt.agent.util.react_parser import ReActOutputParser, ReActStep
from dbgpt.util.configure import DynConfig
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.json_utils import parse_or_raise_error

from ..core.base_agent import _new_system_message
from ..util.agent_errors import (
    ErrorCategory,
    classify_agent_error,
    format_fail_reason,
)
from .actions.react_action import ReActAction, Terminate
from .actions.tool_action import ToolCallSpec, run_tools_batch
from .react_agent import (
    _REACT_DEFAULT_GOAL,
    _REACT_SYSTEM_TEMPLATE,
    _REACT_USER_TEMPLATE,
    _REACT_WRITE_MEMORY_TEMPLATE,
    ReActAgent,
)

logger = logging.getLogger(__name__)


def _build_openai_tools(resource) -> List[Dict[str, Any]]:
    """Build an OpenAI ``tools`` array from the agent's ToolPack.

    Mirrors the JSON-Schema shape that ``BaseTool.get_prompt(prompt_type="openai")``
    produces, but returns the raw ``tools`` array expected by the OpenAI API.
    """
    tool_packs = ToolPack.from_resource(resource)
    tools: List[Dict[str, Any]] = []
    if not tool_packs:
        return tools
    for tool in tool_packs[0].sub_resources:
        if not isinstance(tool, BaseTool):
            continue
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for key, value in tool.args.items():
            properties[key] = {
                "type": value.type,
                "description": value.description,
            }
            if value.required:
                required.append(key)
        # derisk ReActMasterAgentV3-style: inject intent + thought as first-class,
        # optional tool args so native function calling carries a user-facing
        # "意图(做什么)" + "思考(为什么/怎么想)" narration. Keep descriptions
        # minimal (derisk uses "查询意图"/"思考过程") so the model stays terse.
        properties["intention"] = {
            "type": "string",
            "description": "这一步的意图（给用户看，一句话）",
        }
        properties["thought"] = {
            "type": "string",
            "description": "思考过程（给用户看，简短说明）",
        }
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return tools


class ParallelToolAction(ReActAction):
    """ReAct tool action that supports multiple steps per model turn.

    When the model emits more than one actionable ReAct step in a single
    response (common with reasoning models), all steps are executed
    concurrently via :func:`run_tools_batch`. A single-step (or empty)
    response follows the legacy :class:`ReActAction` path exactly.
    """

    def _resolve_step_args(self, step: ReActStep) -> Tuple[Dict[str, Any], str]:
        """Resolve a step's tool arguments without executing the tool.

        Kept in sync with ``ReActAction._do_run`` argument resolution and
        reuses the inherited ``_fallback_parse_args`` /
        ``_extract_html_interpreter_args`` helpers.
        """
        name = step.action
        action_input = step.action_input
        tool_args: Dict[str, Any] = {}
        action_input_str: Any = action_input
        if not name:
            return {}, ""
        try:
            if action_input and isinstance(action_input, str):
                tool_args = parse_or_raise_error(action_input)
            elif isinstance(action_input, dict):
                tool_args = action_input
                action_input_str = json.dumps(action_input, ensure_ascii=False)
            elif isinstance(action_input, list):
                tool_args = {}
                action_input_str = json.dumps(action_input, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            if name == "terminate":
                tool_args = {"output": action_input}
            elif name == "html_interpreter" and isinstance(action_input, str):
                tool_args = self._extract_html_interpreter_args(action_input)
                if not tool_args:
                    tool_args = self._fallback_parse_args(
                        name, action_input, self.resource
                    )
            else:
                tool_args = self._fallback_parse_args(name, action_input, self.resource)
        if not isinstance(tool_args, dict):
            tool_args = {}
        if not isinstance(action_input_str, str):
            action_input_str = json.dumps(action_input_str, ensure_ascii=False)
        return tool_args, action_input_str

    def _parser(self, kwargs: Dict[str, Any]) -> ReActOutputParser:
        parser = kwargs.get("parser")
        if isinstance(parser, ReActOutputParser):
            return parser
        return ReActOutputParser()

    async def run(
        self,
        ai_message: str,
        resource: Optional[Any] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action, batching when the model emitted multiple steps."""
        if not kwargs.get("enable_parallel", False):
            # Parallel execution disabled: preserve the legacy single-action
            # behaviour (ReActAction uses parse_current_step, one tool/round).
            return await super().run(
                ai_message,
                resource=resource,
                rely_action_out=rely_action_out,
                need_vis_render=need_vis_render,
                **kwargs,
            )

        parser = self._parser(kwargs)
        steps = parser.parse(ai_message)
        actionable = [s for s in steps if s.action]

        if len(actionable) <= 1:
            # Zero or one step: preserve the legacy single-tool path exactly.
            return await super().run(
                ai_message,
                resource=resource,
                rely_action_out=rely_action_out,
                need_vis_render=need_vis_render,
                **kwargs,
            )

        specs: List[ToolCallSpec] = []
        for step in actionable:
            tool_args, raw_input = self._resolve_step_args(step)
            specs.append(
                ToolCallSpec(
                    name=step.action,
                    args=tool_args,
                    raw_tool_input=raw_input,
                )
            )
        out = await run_tools_batch(
            specs,
            self.resource,
            self.render_protocol,
            need_vis_render=need_vis_render,
        )

        # Re-attach ReAct metadata (mirrors ReActAction.run post-processing).
        out.thoughts = "\n".join(s.thought for s in actionable if s.thought) or None
        out.phase = next((s.phase for s in actionable if s.phase), None)
        out.action_intention = (
            "\n".join(s.action_intention for s in actionable if s.action_intention)
            or None
        )
        out.action_reason = (
            "\n".join(s.action_reason for s in actionable if s.action_reason) or None
        )
        return out


class NativeToolCallAction(ParallelToolAction):
    """Execute provider-native ``tool_calls`` (function calling) as a ReAct turn.

    When the model returned structured ``tool_calls`` (captured by
    ``ToolCallingReActAgent.thinking`` and passed via ``kwargs["tool_calls"]``),
    each call is executed concurrently via :func:`run_tools_batch`. Otherwise it
    falls back to the text ReAct parsing path of :class:`ParallelToolAction`.
    """

    async def run(
        self,
        ai_message: str,
        resource: Optional[Any] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action from native tool_calls or text fallback."""
        tool_calls = kwargs.get("tool_calls")
        if not tool_calls:
            # No native tool calls — fall back to text ReAct parsing.
            try:
                return await super().run(
                    ai_message,
                    resource=resource,
                    rely_action_out=rely_action_out,
                    need_vis_render=need_vis_render,
                    **kwargs,
                )
            except ValueError as e:
                return ActionOutput(is_exe_success=False, content=str(e))

        specs: List[ToolCallSpec] = []
        intentions: List[str] = []
        thoughts: List[str] = []
        for tc in tool_calls:
            fn = (tc or {}).get("function") or {}
            name = fn.get("name")
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except (json.JSONDecodeError, ValueError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            # derisk-style meta args: strip intention/thought so they never
            # reach the tool's async_execute, but surface them on ActionOutput.
            intention = args.pop("intention", None) or args.pop("intent", None)
            if intention:
                intentions.append(str(intention))
            thought = args.pop("thought", None)
            if thought:
                thoughts.append(str(thought))
            specs.append(ToolCallSpec(name=name, args=args, call_id=tc.get("id")))
        out = await run_tools_batch(
            specs,
            self.resource,
            self.render_protocol,
            need_vis_render=need_vis_render,
        )
        out.action_intention = "\n".join(intentions) or None
        # Prefer the structured thought meta args; fall back to the model's
        # accompanying text (if any) as the reasoning trace.
        if thoughts:
            out.thoughts = "\n".join(thoughts)
        elif ai_message:
            out.thoughts = ai_message
        return out


class ToolCallingReActAgent(ReActAgent):
    """ReAct agent with hermes-style loop enhancements (opt-in by flag).

    Stage 1 capabilities (protocol unchanged):
      - ``enable_parallel_tool_execution``: batch-execute all ReAct steps from
        a single model turn concurrently.
      - ``enable_agent_error_classification``: tag fail reasons with a
        classified category for retry / failover decisions.
    """

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "ToolCallingReAct",
            category="agent",
            key="dbgpt_agent_expand_plugin_tool_calling_agent_name",
        ),
        role=DynConfig(
            "ToolCallingReAct",
            category="agent",
            key="dbgpt_agent_expand_plugin_tool_calling_agent_role",
        ),
        goal=DynConfig(
            _REACT_DEFAULT_GOAL,
            category="agent",
            key="dbgpt_agent_expand_plugin_tool_calling_agent_goal",
        ),
        system_prompt_template=_REACT_SYSTEM_TEMPLATE,
        user_prompt_template=_REACT_USER_TEMPLATE,
        write_memory_template=_REACT_WRITE_MEMORY_TEMPLATE,
    )

    def __init__(self, **kwargs):
        """Init the enhanced ReAct agent."""
        ReActAgent.__init__(self, **kwargs)
        # Re-init actions with the native/parallel-capable tool action. Keeps
        # the same [tool_action, terminate] dispatch contract as ReActAgent.
        self._init_actions([NativeToolCallAction, Terminate])
        # Native function-calling tool calls captured during thinking(); kept
        # on the instance (not a pydantic field) and consumed by act().
        object.__setattr__(self, "_pending_native_tool_calls", None)

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Pass the parser, parallel flag and pending native tool calls to act().

        NOTE: kept synchronous (matching the ``ConversableAgent.prepare_act_param``
        base signature) — the base ``generate_reply`` calls it WITHOUT await, so an
        ``async def`` here returns a coroutine that then blows up
        ``**act_extent_param``.
        """
        ctx = self.agent_context
        return {
            "parser": self.parser,
            "enable_parallel": bool(
                ctx is not None and ctx.enable_parallel_tool_execution
            ),
            "tool_calls": getattr(self, "_pending_native_tool_calls", None),
        }

    async def act(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """Perform actions, relaxing the single-action validation when enabled."""
        ctx = self.agent_context
        parallel_enabled = ctx is not None and ctx.enable_parallel_tool_execution
        native_enabled = ctx is not None and ctx.enable_native_function_calling
        if not (parallel_enabled or native_enabled):
            return await super().act(
                message,
                sender,
                reviewer=reviewer,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
                **kwargs,
            )

        if not message.content and not native_enabled:
            raise ValueError("The response is empty.")
        # Skip ReActAgent.act's "exactly one action per turn" validation and
        # dispatch straight to ConversableAgent.act, which drives the action
        # loop and lets NativeToolCallAction batch-execute the tool calls
        # (native mode) or multiple parsed steps (parallel text mode).
        return await super(ReActAgent, self).act(
            message,
            sender,
            reviewer=reviewer,
            is_retry_chat=is_retry_chat,
            last_speaker_name=last_speaker_name,
            **kwargs,
        )

    async def verify(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:
        """Verify results, tagging failures with a classified category."""
        check, reason = await super().verify(
            message, sender, reviewer=reviewer, **kwargs
        )
        if (
            not check
            and self.agent_context is not None
            and self.agent_context.enable_agent_error_classification
        ):
            category = classify_agent_error(
                reason, default=ErrorCategory.TOOL_EXECUTION
            )
            reason = format_fail_reason(category, reason)
            return False, reason
        return check, reason

    async def thinking(
        self,
        messages: List[AgentMessage],
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
        stream_callback: Optional[Any] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Think, using native function calling when enabled, else text."""
        native_enabled = (
            self.agent_context is not None
            and self.agent_context.enable_native_function_calling
        )
        if native_enabled and self._build_native_tools():
            return await self._thinking_native(
                messages, sender=sender, prompt=prompt, stream_callback=stream_callback
            )

        try:
            return await super().thinking(
                messages, sender=sender, prompt=prompt, stream_callback=stream_callback
            )
        except ValueError as e:
            if (
                self.agent_context is not None
                and self.agent_context.enable_agent_error_classification
            ):
                category = classify_agent_error(e, default=ErrorCategory.RETRYABLE)
                raise ValueError(format_fail_reason(category, str(e)))
            raise

    def _build_native_tools(self) -> List[Dict[str, Any]]:
        """Return the OpenAI tools array for native function calling."""
        return _build_openai_tools(self.resource)

    async def _thinking_native(
        self,
        messages: List[AgentMessage],
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
        stream_callback: Optional[Any] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Native function-calling thinking loop (mirrors base thinking retries)."""
        tools = self._build_native_tools()
        object.__setattr__(self, "_pending_native_tool_calls", None)
        last_model = None
        last_err = None
        retry_count = 0
        llm_messages = [message.to_llm_message() for message in messages]
        while retry_count < 3:
            llm_model = await self._a_select_llm_model(last_model)
            try:
                if prompt:
                    llm_messages = _new_system_message(prompt) + llm_messages
                if not self.llm_client:
                    raise ValueError("LLM client is not initialized!")
                response = await self.llm_client.create_with_output(
                    context=llm_messages[-1].pop("context", None),
                    messages=llm_messages,
                    llm_model=llm_model,
                    max_new_tokens=self.not_null_agent_context.max_new_tokens,
                    temperature=self.not_null_agent_context.temperature,
                    verbose=self.not_null_agent_context.verbose,
                    memory=self.memory.gpts_memory,
                    conv_id=self.not_null_agent_context.conv_id,
                    sender=sender.role if sender else "?",
                    stream_out=self.stream_out,
                    stream_callback=stream_callback,
                    tools=tools,
                    tool_choice="auto",
                )
                text = response.gen_text_with_thinking() if response else ""
                tool_calls = getattr(response, "tool_calls", None) or None
                if tool_calls:
                    object.__setattr__(self, "_pending_native_tool_calls", tool_calls)
                return text, llm_model
            except LLMChatError as e:
                logger.error(f"model:{llm_model} generate Failed!{str(e)}")
                retry_count += 1
                last_model = llm_model
                last_err = str(e)
                await asyncio.sleep(10)

        if last_err:
            raise ValueError(last_err)
        raise ValueError("LLM model inference failed!")
