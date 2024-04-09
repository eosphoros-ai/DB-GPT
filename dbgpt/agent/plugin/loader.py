"""Plugin loader module."""

import logging
from typing import List, Optional

from .generator import PluginPromptGenerator
from .plugins_util import scan_plugins

logger = logging.getLogger(__name__)


class PluginLoader:
    """Plugin Loader Class."""

    def load_plugins(
        self, plugin_path: str, available_plugins: Optional[List[str]] = None
    ) -> PluginPromptGenerator:
        """Load plugins from plugin path."""
        available = available_plugins if available_plugins else ""
        logger.info(f"load_plugin path:{plugin_path}, available:{available}")
        plugins = scan_plugins(plugin_path)

        generator: PluginPromptGenerator = PluginPromptGenerator()
        # load select plugin
        if available_plugins and len(available_plugins) > 0:
            for plugin in plugins:
                if plugin._name in available_plugins:
                    if not plugin.can_handle_post_prompt():
                        continue
                    generator = plugin.post_prompt(generator)
        else:
            for plugin in plugins:
                if not plugin.can_handle_post_prompt():
                    continue
                generator = plugin.post_prompt(generator)
        return generator
