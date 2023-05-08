#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import List

from auto_gpt_plugin_template import AutoGPTPluginTemplate
from pilot.singleton import Singleton

class Config(metaclass=Singleton):
    """Configuration class to store the state of bools for different scripts access"""
    def __init__(self) -> None:
        """Initialize the Config class"""

        # TODO change model_config there
        self.debug_mode = False
        self.execute_local_commands = (
            os.getenv("EXECUTE_LOCAL_COMMANDS", "False") == "True"
        )

        self.plugins_dir = os.getenv("PLUGINS_DIR", 'plugins')
        self.plugins:List[AutoGPTPluginTemplate] = []

    def set_debug_mode(self, value: bool) -> None:
        """Set the debug mode value."""
        self.debug_mode = value

    def set_plugins(self,value: bool) -> None:
        """Set the plugins value."""
        self.plugins = value

  