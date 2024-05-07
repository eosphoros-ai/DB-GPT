"""Resource plugin client API."""
import logging
import os
from typing import Any, Dict, List, Optional, Union, cast

from ..plugin.commands.command_manage import execute_command
from ..plugin.generator import PluginPromptGenerator
from ..plugin.plugins_util import scan_plugin_file, scan_plugins
from ..resource.resource_api import AgentResource
from .resource_api import ResourceClient, ResourceType

logger = logging.getLogger(__name__)


class ResourcePluginClient(ResourceClient):
    """Resource plugin client."""

    @property
    def type(self):
        """Return the resource type."""
        return ResourceType.Plugin

    def get_data_type(self, resource: AgentResource) -> str:
        """Return the data type of the specified resource."""
        return "Tools"

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Get the content introduction prompt of the specified resource."""
        return await self.plugins_prompt(resource.value)

    async def load_plugin(
        self,
        value: str,
        plugin_generator: Optional[PluginPromptGenerator] = None,
    ) -> PluginPromptGenerator:
        """Load the plugin."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def plugins_prompt(
        self, value: str, plugin_generator: Optional[PluginPromptGenerator] = None
    ) -> str:
        """Get the plugin commands prompt."""
        plugin_generator = await self.load_plugin(value)
        return plugin_generator.generate_commands_string()

    async def execute_command(
        self,
        command_name: str,
        arguments: Dict[str, Any],
        plugin_generator: PluginPromptGenerator,
    ):
        """Execute the command."""
        if plugin_generator is None:
            raise ValueError("No plugin commands loaded into the executable！")
        return execute_command(command_name, arguments, plugin_generator)


class PluginFileLoadClient(ResourcePluginClient):
    """File plugin load client.

    Load the plugin from the local file.
    """

    async def load_plugin(
        self, value: str, plugin_generator: Optional[PluginPromptGenerator] = None
    ) -> PluginPromptGenerator:
        """Load the plugin."""
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
                f"The current mode cannot support plug-in loading with relative "
                f"paths: {value}"
            )
        for plugin in plugins:
            if not plugin.can_handle_post_prompt():
                continue
            plugin_generator = plugin.post_prompt(plugin_generator)
        return cast(PluginPromptGenerator, plugin_generator)
