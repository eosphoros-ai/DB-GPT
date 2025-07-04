import json
import logging
from typing import Optional, List

from dbgpt.agent import Action, ActionOutput, AgentResource, Resource, ResourceType
from dbgpt.util.json_utils import parse_or_raise_error

from ...resource.tool.base import BaseTool, ToolParameter
from ...util.react_parser import ReActOutputParser, ReActStep
from .tool_action import ToolAction, run_tool
from dbgpt._private.pydantic import BaseModel, Field, model_to_dict

logger = logging.getLogger(__name__)


class DeepSearchModel(BaseModel):
    """Chart item model."""
    status: str = Field(
        ...,
        description="The status of the current action, can be split_query, summary, or reflection.",
    )
    tools: List[dict] = Field(
        default_factory=list,
        description="List of tools to be used in the action.",
    )
    intention: str = Field(
        ...,
        description="The intention of the current action, describing what you want to achieve.",
    )
    sub_queries: List[str] = Field(
        default_factory=list,
        description="List of sub-queries generated from the current action.",
    )

    def to_dict(self):
        """Convert to dict."""
        return model_to_dict(self)


class DeepSearchAction(ToolAction):
    """React action class."""

    def __init__(self, **kwargs):
        """Tool action init."""
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return None

    @classmethod
    def parse_action(
        cls,
        ai_message: str,
        default_action: "ReActAction",
        resource: Optional[Resource] = None,
        **kwargs,
    ) -> Optional["ReActAction"]:
        """Parse the action from the message.

        If you want skip the action, return None.
        """
        return default_action

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        try:
            action_param: DeepSearchModel = self._input_convert(
                ai_message, DeepSearchModel
            )
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        if action_param.status == "split_query":
            sub_queries = action_param.sub_queries
            # execute knowledge search
            if not action_param.tools:
                return ActionOutput(
                    is_exe_success=False,
                    content="No tools available for knowledge search.",
                )
            if action_param.tools:
                for tool in action_param.tools:
                    if tool.get("tool_type") == "KnowledgeRetrieve":
                        knowledge_args = action_param.get("args", {})
                        if not knowledge_args:
                            return ActionOutput(
                                is_exe_success=False,
                                content="No arguments provided for knowledge search.",
                            )
                        act_out = await self.knowledge_retrieve(
                            sub_queries,
                            knowledge_args,
                            self.resource,
                        )


        # if "parser" in kwargs and isinstance(kwargs["parser"], ReActOutputParser):
        #     parser = kwargs["parser"]
        # else:
        #     parser = ReActOutputParser()
        # steps = parser.parse(ai_message)
        # if len(steps) != 1:
        #     raise ValueError("Only one action is allowed each time.")
        # step = steps[0]
        # act_out = await self._do_run(ai_message, step, need_vis_render=need_vis_render)
        # if not act_out.action:
        #     act_out.action = step.action
        # if step.thought:
        #     act_out.thoughts = step.thought
        # if (
        #     not act_out.action_input
        #     and step.action_input
        #     and isinstance(step.action_input, str)
        # ):
        #     act_out.action_input = step.action_input
        return act_out

    async def knowledge_retrieve(
        self, sub_queries: List[str], knowledge_args: List[str], resource: Resource
    ) -> ActionOutput:
        """Perform knowledge retrieval."""
        query_context_map = {}
        for query in sub_queries:
            resource_prompt, resource_reference = await resource.get_prompt(
                lang=self.language, question=query
            )
            query_context_map[query] = resource_prompt
        action_output = ActionOutput(
            is_exe_success=True,
            content="\n".join([
                f"{query}:{context}" for query, context in query_context_map.items()]
            ),
            view="\n".join([
                f"{query}:{context}" for query, context in query_context_map.items()]
            ),
            observations=query_context_map,
        )
        return action_output




    async def _do_run(
        self,
        ai_message: str,
        parsed_step: ReActStep,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        """Perform the action."""
        tool_args = {}
        name = parsed_step.action
        action_input = parsed_step.action_input
        action_input_str = action_input

        if not name:
            terminal_content = str(action_input_str if action_input_str else ai_message)
            return ActionOutput(
                is_exe_success=True,
                content=terminal_content,
                observations=terminal_content,
                terminate=True,
            )

        try:
            # Try to parse the action input to dict
            if action_input and isinstance(action_input, str):
                tool_args = parse_or_raise_error(action_input)
            elif isinstance(action_input, dict) or isinstance(action_input, list):
                tool_args = action_input
                action_input_str = json.dumps(action_input, ensure_ascii=False)
        except json.JSONDecodeError:
            if parsed_step.action == "terminate":
                tool_args = {"output": action_input}
            logger.warning(f"Failed to parse the args: {action_input}")
        act_out = await run_tool(
            name,
            tool_args,
            self.resource,
            self.render_protocol,
            need_vis_render=need_vis_render,
            raw_tool_input=action_input_str,
        )
        if not act_out.action_input:
            act_out.action_input = action_input_str
        return act_out
