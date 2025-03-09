import json
import logging
from typing import Optional

from dbgpt.agent import ResourceType
from dbgpt.agent.expand.actions.tool_action import ToolAction, ToolInput
from dbgpt.vis import Vis, VisPlugin

logger = logging.getLogger(__name__)


class ReActAction(ToolAction):
    """ReAct action class."""

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
            "Thought": "Summary of thoughts to the user",
            "Action": {
                "tool_name": "The name of a tool that can be used to answer "
                "the current"
                "question or solve the current task.",
                "args": {
                    "arg name1": "arg value1",
                    "arg name2": "arg value2",
                },
            },
        }

        return f"""Please response in the following json format:
        {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
        Make sure the response is correct json and can be parsed by Python json.loads.
        """
