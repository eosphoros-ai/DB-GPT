import logging
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional, Union

from dbgpt.agent.actions.plugin_action import PluginAction
from dbgpt.agent.plugin.generator import PluginPromptGenerator
from dbgpt.agent.resource.resource_api import ResourceType
from dbgpt.agent.resource.resource_plugin_api import ResourcePluginClient

from ..base_agent_new import ConversableAgent

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x


logger = logging.getLogger(__name__)


class PluginAssistantAgent(ConversableAgent):
    plugin_generator: PluginPromptGenerator = None

    name = "LuBan"
    profile: str = "ToolExpert"
    goal: str = (
        "Read and understand the tool information given in the resources below to understand their "
        "capabilities and how to use them,and choosing the right tools to achieve the user's goals."
    )
    constraints: List[str] = [
        "Please read the parameter definition of the tool carefully and extract the specific parameters required to execute the tool from the user gogal.",
        "Please output the selected tool name and specific parameter information in json format according to the following required format. If there is an example, please refer to the sample format output.",
    ]
    desc: str = "You can use the following tools to complete the task objectives, tool information: {tool_infos}"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([PluginAction])

    @property
    def introduce(self, **kwargs):
        return self.desc.format(
            tool_infos=self.plugin_generator.generate_commands_string()
        )

    async def a_preload_resource(self):
        plugin_loader_client: ResourcePluginClient = (
            self.resource_loader.get_resesource_api(ResourceType.Plugin)
        )
        item_list = []
        for item in self.resources:
            if item.type == ResourceType.Plugin:
                item_list.append(item.value)
        self.plugin_generator = await plugin_loader_client.a_load_plugin(
                    item_list, self.plugin_generator
                )

    def prepare_act_param(self) -> Optional[Dict]:
        return {"plugin_generator": self.plugin_generator}
