"""Plugin Assistant Agent."""

import logging
from typing import List, Optional

from .. import Resource, ResourceType
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..resource import BaseTool
from .actions.tool_action import ToolAction

logger = logging.getLogger(__name__)


class ToolAssistantAgent(ConversableAgent):
    """Tool Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "LuBan",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_name",
        ),
        role=DynConfig(
            "ToolExpert",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_role",
        ),
        goal=DynConfig(
            "Read and understand the tool information given in the resources "
            "below to understand their capabilities and how to use them,and choosing "
            "the right tools to achieve the user's goals.",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_goal",
        ),
        constraints=DynConfig(
            [
                "Please read the parameter definition of the tool carefully and extract"
                " the specific parameters required to execute the tool from the user "
                "goal.",
                "Please output the selected tool name and specific parameter "
                "information in json format according to the following required format."
                "If there is an example, please refer to the sample format output.",
                "It is not necessarily required to select a tool for execution. "
                "If the tool to be used or its parameters cannot be clearly "
                "determined based on the user's input, you can choose not to execute.",
            ],
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_constraints",
        ),
        desc=DynConfig(
            "You can use the following tools to complete the task objectives, "
            "tool information: {tool_infos}",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new instance of ToolAssistantAgent."""
        super().__init__(**kwargs)
        self._init_actions([ToolAction])

    @property
    def desc(self) -> Optional[str]:
        """Return desc of this agent."""
        tools = _get_tools_by_resource(self.resource)
        if tools is None or len(tools) == 0:
            return "Has no tools to use"

        tools_desc_list = []
        for i in range(len(tools)):
            tool = tools[i]
            s = f"{i + 1}. tool {tool.name}, can {tool.description}."
            tools_desc_list.append(s)

        return (
            "Can use the following tools to complete the task objectives, "
            "tool information: "
            f"{' '.join(tools_desc_list)}"
        )


def _get_tools_by_resource(resource: Optional[Resource]) -> Optional[List[BaseTool]]:
    tools: List[BaseTool] = []

    if resource is None:
        return tools

    if resource.type() == ResourceType.Tool and isinstance(resource, BaseTool):
        tools.append(resource)
    elif resource.type() == ResourceType.Pack:
        for sub_res in resource.sub_resources:
            res_list = _get_tools_by_resource(sub_res)
            if res_list is not None and len(res_list) > 0:
                tools.extend(_get_tools_by_resource(sub_res))

    return tools
