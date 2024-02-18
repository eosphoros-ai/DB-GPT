import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt._private.config import Config
from dbgpt.agent.plugin.generator import PluginPromptGenerator
from dbgpt.agent.resource.resource_plugin_api import ResourcePluginClient
from dbgpt.component import ComponentType
from dbgpt.serve.agent.hub.controller import ModulePlugin
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace

CFG = Config()

logger = logging.getLogger(__name__)


class PluginHubLoadClient(ResourcePluginClient):
    def __init__(self):
        super().__init__()
        # The executor to submit blocking function
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

    async def a_load_plugin(
        self, value: str, plugin_generator: Optional[PluginPromptGenerator] = None
    ) -> PluginPromptGenerator:
        logger.info(f"PluginHubLoadClient load plugin:{value}")
        plugins_prompt_generator = PluginPromptGenerator()
        plugins_prompt_generator.command_registry = CFG.command_registry

        agent_module = CFG.SYSTEM_APP.get_component(
            ComponentType.PLUGIN_HUB, ModulePlugin
        )
        plugins_prompt_generator = agent_module.load_select_plugin(
            plugins_prompt_generator, json.dumps(value)
        )

        return plugins_prompt_generator
