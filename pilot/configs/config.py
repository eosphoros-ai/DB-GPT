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
        self.skip_reprompt = False
        
        self.plugins_dir = os.getenv("PLUGINS_DIR", "plugins")
        self.plugins = List[AutoGPTPluginTemplate] = []
        self.temperature = float(os.getenv("TEMPERATURE", 0.7))

        # TODO change model_config there
        self.execute_local_commands = (
            os.getenv("EXECUTE_LOCAL_COMMANDS", "False") == "True"
        )
        # User agent header to use when making HTTP requests
        # Some websites might just completely deny request with an error code if
        # no user agent was found.
        self.user_agent = os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
        )
        
        # milvus or zilliz cloud configuration
        self.milvus_addr = os.getenv("MILVUS_ADDR", "localhost:19530")
        self.milvus_username = os.getenv("MILVUS_USERNAME")
        self.milvus_password = os.getenv("MILVUS_PASSWORD")
        self.milvus_collection = os.getenv("MILVUS_COLLECTION", "dbgpt")
        self.milvus_secure = os.getenv("MILVUS_SECURE") == "True"

        plugins_allowlist = os.getenv("ALLOWLISTED_PLUGINS")
        if plugins_allowlist:
            self.plugins_allowlist = plugins_allowlist.split(",")
        else:
            self.plugins_allowlist = [] 

        plugins_denylist = os.getenv("DENYLISTED_PLUGINS") 
        if plugins_denylist:
            self.plugins_denylist = []
    
    def set_debug_mode(self, value: bool) -> None:
        """Set the debug mode value"""
        self.debug_mode = value

    def set_plugins(self, value: list) -> None:
        """Set the plugins value. """
        self.plugins = value

    def set_templature(self, value: int) -> None:
        """Set the temperature value."""
        self.temperature = value

    