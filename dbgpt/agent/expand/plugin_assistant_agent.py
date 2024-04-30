"""Plugin Assistant Agent."""

import logging
from typing import Any, Dict, Optional

from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..plugin.generator import PluginPromptGenerator
from ..resource.resource_api import ResourceType
from ..resource.resource_plugin_api import ResourcePluginClient
from .actions.plugin_action import PluginAction

logger = logging.getLogger(__name__)


class PluginAssistantAgent(ConversableAgent):
    """Plugin Assistant Agent."""

    plugin_generator: Optional[PluginPromptGenerator] = None

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
        """Create a new instance of PluginAssistantAgent."""
        super().__init__(**kwargs)
        self._init_actions([PluginAction])

    # @property
    # def introduce(self, **kwargs) -> str:
    #     """Introduce the agent."""
    #     if not self.plugin_generator:
    #         raise ValueError("PluginGenerator is not loaded.")
    #     return self.desc.format(
    #         tool_infos=self.plugin_generator.generate_commands_string()
    #     )

    async def preload_resource(self):
        """Preload the resource."""
        plugin_loader_client: ResourcePluginClient = (
            self.not_null_resource_loader.get_resource_api(
                ResourceType.Plugin, ResourcePluginClient
            )
        )
        item_list = []
        for item in self.resources:
            if item.type == ResourceType.Plugin:
                item_list.append(item.value)
        plugin_generator = self.plugin_generator
        for item in item_list:
            plugin_generator = await plugin_loader_client.load_plugin(
                item, plugin_generator
            )
        self.plugin_generator = plugin_generator

    def prepare_act_param(self) -> Dict[str, Any]:
        """Prepare the act parameter."""
        return {"plugin_generator": self.plugin_generator}
