#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from auto_gpt_plugin_template import AutoGPTPluginTemplate
from pilot.singleton import Singleton

class Config(metaclass=Singleton):
    """Configuration class to store the state of bools for different scripts access"""
    def __init__(self) -> None:
        """Initialize the Config class"""
        pass

