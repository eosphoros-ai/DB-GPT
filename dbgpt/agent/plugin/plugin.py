import logging
from typing import List

from .generator import PluginPromptGenerator

logger = logging.getLogger(__name__)


class PluginLoader:
    def load_plugins(
        self, generator: PluginPromptGenerator, my_plugins: List[str]
    ) -> PluginPromptGenerator:
        logger.info(f"load_select_plugin:{my_plugins}")
        # load select plugin
        for plugin in self.plugins:
            if plugin._name in my_plugins:
                if not plugin.can_handle_post_prompt():
                    continue
                generator = plugin.post_prompt(generator)
        return generator
