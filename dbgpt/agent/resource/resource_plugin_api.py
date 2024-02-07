import logging
import os
from typing import Optional

from dbgpt.agent.plugin.commands.command_mange import execute_command
from dbgpt.agent.plugin.generator import PluginPromptGenerator
from dbgpt.agent.plugin.plugins_util import scan_plugin_file, scan_plugins
from dbgpt.agent.resource.resource_api import AgentResource

from .resource_api import ResourceClient, ResourceType

logger = logging.getLogger(__name__)


class ResourcePluginClient(ResourceClient):
    @property
    def type(self):
        return ResourceType.Plugin

    def get_data_type(self, resource: AgentResource) -> str:
        return "Tools"

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> str:
        return await self.a_plugins_prompt(resource.value)

    async def a_load_plugin(
        self,
        value: str,
        plugin_generator: Optional[PluginPromptGenerator] = None,
    ) -> PluginPromptGenerator:
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def a_plugins_prompt(
        self, value: str, plugin_generator: Optional[PluginPromptGenerator] = None
    ) -> str:
        plugin_generator = await self.a_load_plugin(value)
        return plugin_generator.generate_commands_string()

    async def a_execute_command(
        self,
        command_name: str,
        arguments: Optional[dict],
        plugin_generator: Optional[PluginPromptGenerator],
    ):
        if plugin_generator is None:
            raise ValueError("No plugin commands loaded into the executable！")
        return execute_command(command_name, arguments, plugin_generator)


class PluginFileLoadClient(ResourcePluginClient):
    async def a_load_plugin(
        self, value: str, plugin_generator: Optional[PluginPromptGenerator] = None
    ) -> PluginPromptGenerator:
        logger.info(f"PluginFileLoadClient load plugin:{value}")
        if plugin_generator is None:
            plugin_generator = PluginPromptGenerator()
        plugins = []
        if os.path.isabs(value):
            if not os.path.exists(value):
                raise ValueError(f"Wrong plugin file path configured {value}!")
            if os.path.isfile(value):
                plugins.extend(scan_plugin_file(value))
            else:
                plugins.extend(scan_plugins(value))
        else:
            raise ValueError(
                f"The current mode cannot support plug-in loading with relative paths.{value}"
            )
        for plugin in plugins:
            if not plugin.can_handle_post_prompt():
                continue
            plugin_generator = plugin.post_prompt(plugin_generator)
        return plugin_generator
