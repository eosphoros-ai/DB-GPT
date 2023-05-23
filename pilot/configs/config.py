#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import nltk
from typing import List

from auto_gpt_plugin_template import AutoGPTPluginTemplate
from pilot.singleton import Singleton


class Config(metaclass=Singleton):
    """Configuration class to store the state of bools for different scripts access"""
    def __init__(self) -> None:
        """Initialize the Config class"""

        self.debug_mode = False
        self.skip_reprompt = False
        self.temperature = float(os.getenv("TEMPERATURE", 0.7))


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

        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_voice_1_id = os.getenv("ELEVENLABS_VOICE_1_ID")
        self.elevenlabs_voice_2_id = os.getenv("ELEVENLABS_VOICE_2_ID")

        self.use_mac_os_tts = False
        self.use_mac_os_tts = os.getenv("USE_MAC_OS_TTS")

        # milvus or zilliz cloud configuration
        self.milvus_addr = os.getenv("MILVUS_ADDR", "localhost:19530")
        self.milvus_username = os.getenv("MILVUS_USERNAME")
        self.milvus_password = os.getenv("MILVUS_PASSWORD")
        self.milvus_collection = os.getenv("MILVUS_COLLECTION", "dbgpt")
        self.milvus_secure = os.getenv("MILVUS_SECURE") == "True"


        self.authorise_key = os.getenv("AUTHORISE_COMMAND_KEY", "y")
        self.exit_key = os.getenv("EXIT_KEY", "n")
        self.image_provider = os.getenv("IMAGE_PROVIDER", True)
        self.image_size = int(os.getenv("IMAGE_SIZE", 256))

        self.huggingface_api_token = os.getenv("HUGGINGFACE_API_TOKEN")
        self.image_provider = os.getenv("IMAGE_PROVIDER")
        self.image_size = int(os.getenv("IMAGE_SIZE", 256))
        self.huggingface_image_model = os.getenv(
            "HUGGINGFACE_IMAGE_MODEL", "CompVis/stable-diffusion-v1-4"
        )
        self.huggingface_audio_to_text_model = os.getenv(
            "HUGGINGFACE_AUDIO_TO_TEXT_MODEL"
        )
        self.speak_mode = False


        ### Related configuration of built-in commands
        self.command_registry = []

        disabled_command_categories = os.getenv("DISABLED_COMMAND_CATEGORIES")
        if disabled_command_categories:
            self.disabled_command_categories = disabled_command_categories.split(",")
        else:
            self.disabled_command_categories = []

        self.execute_local_commands = (
            os.getenv("EXECUTE_LOCAL_COMMANDS", "False") == "True"
        )


        ### The associated configuration parameters of the plug-in control the loading and use of the plug-in
        self.plugins_dir = os.getenv("PLUGINS_DIR", "../../plugins")
        self.plugins: List[AutoGPTPluginTemplate] = []
        self.plugins_openai = []

        plugins_allowlist = os.getenv("ALLOWLISTED_PLUGINS")
        if plugins_allowlist:
            self.plugins_allowlist = plugins_allowlist.split(",")
        else:
            self.plugins_allowlist = []

        plugins_denylist = os.getenv("DENYLISTED_PLUGINS")
        if plugins_denylist:
            self.plugins_denylist = plugins_denylist.split(",")
        else:
            self.plugins_denylist = []


        ### Local database connection configuration
        self.LOCAL_DB_HOST =  os.getenv("LOCAL_DB_HOST",  "127.0.0.1")
        self.LOCAL_DB_PORT =  int(os.getenv("LOCAL_DB_PORT",  3306))
        self.LOCAL_DB_USER =  os.getenv("LOCAL_DB_USER",  "root")
        self.LOCAL_DB_PASSWORD =  os.getenv("LOCAL_DB_PASSWORD",  "aa123456")

        ### LLM Model Service Configuration
        self.LLM_MODEL = os.getenv("LLM_MODEL",  "vicuna-13b")
        self.LIMIT_MODEL_CONCURRENCY = int(os.getenv("LIMIT_MODEL_CONCURRENCY",  5))
        self.MAX_POSITION_EMBEDDINGS = int(os.getenv("MAX_POSITION_EMBEDDINGS",  4096))
        self.MODEL_PORT = os.getenv("MODEL_PORT",  8000)
        self.MODEL_SERVER = os.getenv("MODEL_SERVER",  "http://127.0.0.1" + ":" + str(self.MODEL_PORT))
        self.ISLOAD_8BIT = os.getenv("ISLOAD_8BIT", "True") == "True"

        ### Vector Store Configuration
        self.VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE",  "Chroma")
        self.MILVUS_URL = os.getenv("MILVUS_URL",  "127.0.0.1")
        self.MILVUS_PORT = os.getenv("MILVUS_PORT",  "19530")
        self.MILVUS_USERNAME = os.getenv("MILVUS_USERNAME",  None)
        self.MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD",  None)


    def set_debug_mode(self, value: bool) -> None:
        """Set the debug mode value"""
        self.debug_mode = value

    def set_plugins(self, value: list) -> None:
        """Set the plugins value. """
        self.plugins = value

    def set_templature(self, value: int) -> None:
        """Set the temperature value."""
        self.temperature = value

    def set_speak_mode(self, value: bool) -> None:
        """Set the speak mode value."""
        self.speak_mode = value

    def set_last_plugin_return(self, value: bool) -> None:
        """Set the speak mode value."""
        self.last_plugin_return = value