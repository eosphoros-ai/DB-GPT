import json
import logging
from typing import Optional

from dbgpt.agent import ActionOutput, AgentResource, Resource

from ...util.react_parser import ReActOutputParser
from .tool_action import ToolAction, run_tool

logger = logging.getLogger(__name__)


class ReActAction(ToolAction):
    """React action class."""

    def __init__(self, **kwargs):
        """Tool action init."""
        super().__init__(**kwargs)

    @classmethod
    def parse_action(
        cls,
        ai_message: str,
        default_action: "ReActAction",
        resource: Optional[Resource] = None,
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
        parser = ReActOutputParser()
        steps = parser.parse(ai_message)
        if len(steps) != 1:
            raise ValueError("Only one action is allowed each time.")
        step = steps[0]
        name = step.action
        action_input = step.action_input
        action_input_str = action_input
        thought = step.thought
        tool_args = {}
        try:
            if action_input and isinstance(action_input, str):
                tool_args = json.loads(action_input)
            elif isinstance(action_input, dict):
                tool_args = action_input
                action_input_str = json.dumps(action_input, ensure_ascii=False)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse the args: {action_input}")
        act_out = await run_tool(
            name,
            tool_args,
            self.resource,
            self.render_protocol,
            need_vis_render=need_vis_render,
        )
        if not act_out.action:
            act_out.action = name
        if not act_out.action_input:
            act_out.action_input = action_input_str
        if thought:
            act_out.thoughts = thought
        return act_out
