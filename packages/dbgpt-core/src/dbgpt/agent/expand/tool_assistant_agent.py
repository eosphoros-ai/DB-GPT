"""Plugin Assistant Agent."""

import logging

from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
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
                " If there is an example, please refer to the sample format output.",
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
