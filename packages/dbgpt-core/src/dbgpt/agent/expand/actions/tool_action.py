"""Plugin Action Module."""

import asyncio
import dataclasses
import json
import logging
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

from ...core.action.base import Action, ActionOutput
from ...core.context.storage import get_current_storage
from ...core.schema import Status
from ...resource.base import AgentResource, Resource, ResourceType
from ...resource.tool.pack import ToolPack

logger = logging.getLogger(__name__)


class ToolInput(BaseModel):
    """Plugin input model."""

    tool_name: str = Field(
        ...,
        description="The name of a tool that can be used to answer the current question"
        " or solve the current task.",
    )
    args: dict = Field(
        default={"arg name1": "", "arg name2": ""},
        description="The tool selected for the current target, the parameter "
        "information required for execution",
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class ToolAction(Action[ToolInput]):
    """Tool action class."""

    def __init__(self, **kwargs):
        """Tool action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return ResourceType.Tool

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return ToolInput

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        out_put_schema = {
            "thought": "Summary of thoughts to the user",
            "tool_name": "The name of a tool that can be used to answer the current "
            "question or solve the current task.",
            "args": {
                "arg name1": "arg value1",
                "arg name2": "arg value2",
            },
        }

        return f"""Please response in the following json format:
        {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
        Make sure the response is correct json and can be parsed by Python json.loads.
        """

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the plugin action.

        Args:
            ai_message (str): The AI message.
            resource (Optional[AgentResource], optional): The resource. Defaults to
                None.
            rely_action_out (Optional[ActionOutput], optional): The rely action output.
                Defaults to None.
            need_vis_render (bool, optional): Whether need visualization rendering.
                Defaults to True.
        """
        try:
            param: ToolInput = self._input_convert(ai_message, ToolInput)
            return await run_tool(
                param.tool_name,
                param.args,
                self.resource,
                self.render_protocol,
                need_vis_render=need_vis_render,
            )
        except Exception as e:
            # If the LLM didn't produce the strict JSON schema, try some
            # pragmatic fallbacks so agents can still execute the intended tool:
            # 1) If the AI output is a plain numeric string, accept it as result.
            # 2) Try to extract a tool name and an `expression` enclosed in backticks
            #    (common pattern: "Use `calculate` with expression `10 * 99`").
            # 3) Otherwise return a helpful failure ActionOutput.
            logger.debug(
                "ToolAction JSON parse failed, attempting fallbacks: %s", str(e)
            )

            text = ai_message or ""
            text = text.strip().strip('"')

            # Fallback 1: pure numeric result
            import re

            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
                return ActionOutput(
                    is_exe_success=True,
                    content=text,
                    observations=text,
                )

            # Fallback 2: extract tool name and expression in backticks
            tool_name = None
            expr = None
            m_tool = re.search(r"`([A-Za-z0-9_-]+)`", text)
            if m_tool:
                tool_name = m_tool.group(1)
            m_expr = re.search(r"expression\s+`([^`]+)`", text, re.IGNORECASE)
            if m_expr:
                expr = m_expr.group(1)

            # If we found an expression, call the tool with that expression
            if expr:
                try:
                    chosen_tool = tool_name or "calculate"
                    return await run_tool(
                        chosen_tool,
                        {"expression": expr},
                        self.resource,
                        self.render_protocol,
                        need_vis_render=need_vis_render,
                        raw_tool_input=None,
                    )
                except Exception:
                    logger.exception("Fallback tool execution failed")

            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )


async def run_tool(
    name: str,
    args: dict,
    resource: Resource,
    render_protocol: Optional[Vis] = None,
    need_vis_render: bool = False,
    raw_tool_input: Optional[str] = None,
) -> ActionOutput:
    """Run the tool."""
    is_terminal = None
    try:
        tool_packs = ToolPack.from_resource(resource)
        if not tool_packs:
            raise ValueError("The tool resource is not found！")
        tool_pack: ToolPack = tool_packs[0]
        response_success = True
        status = Status.RUNNING.value
        err_msg = None

        if raw_tool_input and args is not None:
            try:
                parsed = tool_pack.parse_execute_args(
                    resource_name=name, input_str=raw_tool_input
                )
                if parsed and isinstance(parsed, tuple):
                    args = parsed[1]
                if args is not None and isinstance(args, list) and len(args) == 0:
                    args = {}
            except Exception:
                pass

        try:
            tool_result = await tool_pack.async_execute(resource_name=name, **args)
            status = Status.COMPLETE.value
            is_terminal = tool_pack.is_terminal(name)
        except Exception as e:
            response_success = False
            logger.exception(f"Tool [{name}] execute failed!")
            status = Status.FAILED.value
            err_msg = f"Tool [{name}] execute failed! {str(e)}"
            tool_result = err_msg

        result_str = str(tool_result)

        # Layer 2: persist oversized tool results to disk and replace the
        # in-context content with a <persisted-output> preview + file path.
        # The full content is retained in `observations` for DB persistence.
        persisted_path: Optional[str] = None
        in_context_content = result_str
        storage = get_current_storage()
        if storage is not None and response_success:
            try:
                replacement, persisted_path = storage.maybe_persist(
                    content=result_str,
                    tool_name=name,
                    tool_call_id=f"{name}_{id(tool_result):x}",
                )
                if persisted_path:
                    in_context_content = replacement
            except Exception:
                logger.exception(
                    "Tool result persistence failed for %s; using full content",
                    name,
                )
                persisted_path = None
                in_context_content = result_str

        plugin_param = {
            "name": name,
            "args": args,
            "status": status,
            "logo": None,
            "result": in_context_content,
            "err_msg": err_msg,
        }
        if render_protocol:
            view = await render_protocol.display(content=plugin_param)
        elif need_vis_render:
            raise NotImplementedError("The render_protocol should be implemented.")
        else:
            view = None

        return ActionOutput(
            is_exe_success=response_success,
            content=in_context_content,
            view=view,
            observations=result_str,
            terminate=is_terminal,
            persisted_path=persisted_path,
        )
    except Exception as e:
        logger.exception("Tool Action Run Failed！")
        return ActionOutput(
            is_exe_success=False,
            content=f"Tool action run failed!{str(e)}",
            terminate=is_terminal,
        )


@dataclasses.dataclass
class ToolCallSpec:
    """A single tool invocation for batch (parallel) execution.

    Attributes:
        name: The tool name, looked up in the agent's ``ToolPack``.
        args: The tool arguments (already resolved to a dict).
        call_id: Optional provider-native tool call id. Only populated in the
            stage-2 native-function-calling path; ``None`` for the text path.
        raw_tool_input: The raw model-produced argument string, used by
            :func:`run_tool` to re-parse arguments when ``args`` is empty.
    """

    name: str
    args: Dict[str, Any] = dataclasses.field(default_factory=dict)
    call_id: Optional[str] = None
    raw_tool_input: Optional[str] = None


async def run_tools_batch(
    specs: List[ToolCallSpec],
    resource: Resource,
    render_protocol: Optional[Vis] = None,
    need_vis_render: bool = False,
) -> ActionOutput:
    """Execute multiple tool calls concurrently and aggregate into one output.

    A one-element batch is forwarded verbatim to :func:`run_tool`, so batch
    mode is a strict superset of the legacy single-tool behaviour (no change to
    the existing per-tool path).

    Aggregation contract (mapping onto :class:`ActionOutput`):
      - is_exe_success: ``all`` — a failed tool surfaces to the model on the
        next retry round via the joined ``content``.
      - content: per-tool in-context previews joined by blank lines.
      - observations: JSON array of per-tool result dicts (round-trippable by
        the structured memory fragment / read_memories).
      - terminate: ``any`` terminal tool.
      - have_retry: ``any`` (defaults True for every tool).
      - view: concatenated vis-plugin blocks when rendering was requested.
    """
    if not specs:
        return ActionOutput(
            is_exe_success=False,
            content="No tool calls to execute.",
            observations="[]",
        )
    if len(specs) == 1:
        spec = specs[0]
        out = await run_tool(
            name=spec.name,
            args=spec.args,
            resource=resource,
            render_protocol=render_protocol,
            need_vis_render=need_vis_render,
            raw_tool_input=spec.raw_tool_input,
        )
        # run_tool omits `action` (unlike the multi-branch below) — backfill it
        # so native single-tool turns still carry the tool name on ActionOutput.
        if not getattr(out, "action", None):
            out.action = spec.name
        return out

    async def _run_one(spec: ToolCallSpec) -> ActionOutput:
        try:
            out: ActionOutput = await run_tool(
                name=spec.name,
                args=spec.args,
                resource=resource,
                render_protocol=render_protocol,
                need_vis_render=need_vis_render,
                raw_tool_input=spec.raw_tool_input,
            )
        except Exception as e:  # pragma: no cover - run_tool already guards
            out = ActionOutput(
                is_exe_success=False,
                content=f"Tool [{spec.name}] execute failed! {str(e)}",
                observations=f"Tool [{spec.name}] execute failed! {str(e)}",
            )
        if not out.action:
            out.action = spec.name
        return out

    outputs: List[ActionOutput] = list(
        await asyncio.gather(
            *(_run_one(spec) for spec in specs), return_exceptions=True
        )
    )

    # Normalise exceptions returned by gather (defensive; _run_one already
    # converts its own failures into a failure ActionOutput).
    normalized: List[ActionOutput] = []
    for spec, out in zip(specs, outputs):
        if isinstance(out, BaseException):
            normalized.append(
                ActionOutput(
                    is_exe_success=False,
                    content=f"Tool [{spec.name}] execute failed! {out}",
                    observations=f"Tool [{spec.name}] execute failed! {out}",
                    action=spec.name,
                )
            )
        else:
            normalized.append(out)

    is_exe_success = all(o.is_exe_success for o in normalized)
    terminate = any(o.terminate is True for o in normalized)
    have_retry = any(o.have_retry for o in normalized)

    content = "\n\n".join(o.content for o in normalized)
    views = [o.view for o in normalized if o.view]

    tool_results: List[Dict[str, Any]] = [
        {
            "name": spec.name,
            "call_id": spec.call_id,
            "success": out.is_exe_success,
            "content": out.content,
            "observation": out.observations,
            "terminate": out.terminate,
            "persisted_path": out.persisted_path,
        }
        for spec, out in zip(specs, normalized)
    ]

    return ActionOutput(
        is_exe_success=is_exe_success,
        content=content,
        view="\n".join(views) if views else None,
        action=", ".join(spec.name for spec in specs),
        action_input=json.dumps([spec.args for spec in specs], ensure_ascii=False),
        observations=json.dumps(tool_results, ensure_ascii=False),
        have_retry=have_retry,
        terminate=terminate if terminate else None,
    )
