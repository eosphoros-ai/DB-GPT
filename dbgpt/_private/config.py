#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

from dbgpt.util.singleton import Singleton

if TYPE_CHECKING:
    from auto_gpt_plugin_template import AutoGPTPluginTemplate

    from dbgpt.component import SystemApp
    from dbgpt.datasource.manages import ConnectorManager


class Config(metaclass=Singleton):
    """Configuration class to store the state of bools for different scripts access"""

    def __init__(self) -> None:
        """Initialize the Config class"""

        self.NEW_SERVER_MODE = False
        self.SERVER_LIGHT_MODE = False

        # Gradio language version: en, zh
        self.LANGUAGE = os.getenv("LANGUAGE", "en")
        self.WEB_SERVER_PORT = int(os.getenv("WEB_SERVER_PORT", 7860))

        self.debug_mode = False
        self.skip_reprompt = False
        self.temperature = float(os.getenv("TEMPERATURE", 0.7))

        # self.NUM_GPUS = int(os.getenv("NUM_GPUS", 1))

        self.execute_local_commands = (
            os.getenv("EXECUTE_LOCAL_COMMANDS", "False").lower() == "true"
        )
        # User agent header to use when making HTTP requests
        # Some websites might just completely deny request with an error code if
        # no user agent was found.
        self.user_agent = os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
        )

        # This is a proxy server, just for test_py.  we will remove this later.
        self.proxy_api_key = os.getenv("PROXY_API_KEY")
        self.bard_proxy_api_key = os.getenv("BARD_PROXY_API_KEY")

        # In order to be compatible with the new and old model parameter design
        if self.bard_proxy_api_key:
            os.environ["bard_proxyllm_proxy_api_key"] = self.bard_proxy_api_key

        # tongyi
        self.tongyi_proxy_api_key = os.getenv("TONGYI_PROXY_API_KEY")
        if self.tongyi_proxy_api_key:
            os.environ["tongyi_proxyllm_proxy_api_key"] = self.tongyi_proxy_api_key

        # zhipu
        self.zhipu_proxy_api_key = os.getenv("ZHIPU_PROXY_API_KEY")
        if self.zhipu_proxy_api_key:
            os.environ["zhipu_proxyllm_proxy_api_key"] = self.zhipu_proxy_api_key
            os.environ["zhipu_proxyllm_proxyllm_backend"] = os.getenv(
                "ZHIPU_MODEL_VERSION", ""
            )

        # wenxin
        self.wenxin_proxy_api_key = os.getenv("WEN_XIN_API_KEY")
        self.wenxin_proxy_api_secret = os.getenv("WEN_XIN_API_SECRET")
        self.wenxin_model_version = os.getenv("WEN_XIN_MODEL_VERSION")
        if self.wenxin_proxy_api_key and self.wenxin_proxy_api_secret:
            os.environ["wenxin_proxyllm_proxy_api_key"] = self.wenxin_proxy_api_key
            os.environ[
                "wenxin_proxyllm_proxy_api_secret"
            ] = self.wenxin_proxy_api_secret
            os.environ["wenxin_proxyllm_proxyllm_backend"] = (
                self.wenxin_model_version or ""
            )

        # xunfei spark
        self.spark_api_version = os.getenv("XUNFEI_SPARK_API_VERSION")
        self.spark_proxy_api_key = os.getenv("XUNFEI_SPARK_API_KEY")
        self.spark_proxy_api_secret = os.getenv("XUNFEI_SPARK_API_SECRET")
        self.spark_proxy_api_appid = os.getenv("XUNFEI_SPARK_APPID")
        if self.spark_proxy_api_key and self.spark_proxy_api_secret:
            os.environ["spark_proxyllm_proxy_api_key"] = self.spark_proxy_api_key
            os.environ["spark_proxyllm_proxy_api_secret"] = self.spark_proxy_api_secret
            os.environ["spark_proxyllm_proxyllm_backend"] = self.spark_api_version or ""
            os.environ["spark_proxyllm_proxy_api_app_id"] = (
                self.spark_proxy_api_appid or ""
            )

        # baichuan proxy
        self.bc_proxy_api_key = os.getenv("BAICHUAN_PROXY_API_KEY")
        self.bc_model_name = os.getenv("BAICHUN_MODEL_NAME", "Baichuan2-Turbo-192k")
        if self.bc_proxy_api_key and self.bc_model_name:
            os.environ["bc_proxyllm_proxy_api_key"] = self.bc_proxy_api_key
            os.environ["bc_proxyllm_proxyllm_backend"] = self.bc_model_name

        # gemini proxy
        self.gemini_proxy_api_key = os.getenv("GEMINI_PROXY_API_KEY")
        if self.gemini_proxy_api_key:
            os.environ["gemini_proxyllm_proxy_api_key"] = self.gemini_proxy_api_key
            os.environ["gemini_proxyllm_proxyllm_backend"] = os.getenv(
                "GEMINI_MODEL_VERSION", "gemini-pro"
            )

        # Yi proxy
        self.yi_proxy_api_key = os.getenv("YI_API_KEY")
        if self.yi_proxy_api_key:
            os.environ["yi_proxyllm_proxy_api_key"] = self.yi_proxy_api_key
            os.environ["yi_proxyllm_proxyllm_backend"] = os.getenv(
                "YI_MODEL_VERSION", "yi-34b-chat-0205"
            )
            os.environ["yi_proxyllm_proxy_api_base"] = os.getenv(
                "YI_API_BASE", "https://api.lingyiwanwu.com/v1"
            )

        self.proxy_server_url = os.getenv("PROXY_SERVER_URL")

        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_voice_1_id = os.getenv("ELEVENLABS_VOICE_1_ID")
        self.elevenlabs_voice_2_id = os.getenv("ELEVENLABS_VOICE_2_ID")

        self.use_mac_os_tts = os.getenv("USE_MAC_OS_TTS", "False") == "True"

        self.authorise_key = os.getenv("AUTHORISE_COMMAND_KEY", "y")
        self.exit_key = os.getenv("EXIT_KEY", "n")
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

        from dbgpt.core._private.prompt_registry import PromptTemplateRegistry

        self.prompt_template_registry = PromptTemplateRegistry()
        ### Related configuration of built-in commands
        self.command_registry = []  # type: ignore

        disabled_command_categories = os.getenv("DISABLED_COMMAND_CATEGORIES")
        if disabled_command_categories:
            self.disabled_command_categories = disabled_command_categories.split(",")
        else:
            self.disabled_command_categories = []

        self.execute_local_commands = (
            os.getenv("EXECUTE_LOCAL_COMMANDS", "False").lower() == "true"
        )
        ### message stor file
        self.message_dir = os.getenv("MESSAGE_HISTORY_DIR", "../../message")

        ### The associated configuration parameters of the plug-in control the loading and use of the plug-in

        self.plugins: List["AutoGPTPluginTemplate"] = []
        self.plugins_openai = []  # type: ignore
        self.plugins_auto_load = os.getenv("AUTO_LOAD_PLUGIN", "True").lower() == "true"

        self.plugins_git_branch = os.getenv("PLUGINS_GIT_BRANCH", "plugin_dashboard")

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
        ### Native SQL Execution Capability Control Configuration
        self.NATIVE_SQL_CAN_RUN_DDL = (
            os.getenv("NATIVE_SQL_CAN_RUN_DDL", "True").lower() == "true"
        )
        self.NATIVE_SQL_CAN_RUN_WRITE = (
            os.getenv("NATIVE_SQL_CAN_RUN_WRITE", "True").lower() == "true"
        )

        ###dbgpt meta info database connection configuration
        self.LOCAL_DB_HOST = os.getenv("LOCAL_DB_HOST")
        self.LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "data/default_sqlite.db")
        self.LOCAL_DB_TYPE = os.getenv("LOCAL_DB_TYPE", "sqlite")
        if self.LOCAL_DB_HOST is None and self.LOCAL_DB_PATH == "":
            self.LOCAL_DB_HOST = "127.0.0.1"

        self.LOCAL_DB_NAME = os.getenv("LOCAL_DB_NAME", "dbgpt")
        self.LOCAL_DB_PORT = int(os.getenv("LOCAL_DB_PORT", 3306))
        self.LOCAL_DB_USER = os.getenv("LOCAL_DB_USER", "root")
        self.LOCAL_DB_PASSWORD = os.getenv("LOCAL_DB_PASSWORD", "aa123456")
        self.LOCAL_DB_POOL_SIZE = int(os.getenv("LOCAL_DB_POOL_SIZE", 10))
        self.LOCAL_DB_POOL_OVERFLOW = int(os.getenv("LOCAL_DB_POOL_OVERFLOW", 20))

        self.CHAT_HISTORY_STORE_TYPE = os.getenv("CHAT_HISTORY_STORE_TYPE", "db")

        ### LLM Model Service Configuration
        self.LLM_MODEL = os.getenv("LLM_MODEL", "vicuna-13b-v1.5")
        self.LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH")

        ### Proxy llm backend, this configuration is only valid when "LLM_MODEL=proxyllm"
        ### When we use the rest API provided by deployment frameworks like fastchat as a proxyllm, "PROXYLLM_BACKEND" is the model they actually deploy.
        ### We need to use "PROXYLLM_BACKEND" to load the prompt of the corresponding scene.
        self.PROXYLLM_BACKEND = None
        if self.LLM_MODEL == "proxyllm":
            self.PROXYLLM_BACKEND = os.getenv("PROXYLLM_BACKEND")

        self.LIMIT_MODEL_CONCURRENCY = int(os.getenv("LIMIT_MODEL_CONCURRENCY", 5))
        self.MAX_POSITION_EMBEDDINGS = int(os.getenv("MAX_POSITION_EMBEDDINGS", 4096))
        self.MODEL_PORT = os.getenv("MODEL_PORT", 8000)
        self.MODEL_SERVER = os.getenv(
            "MODEL_SERVER", "http://127.0.0.1" + ":" + str(self.MODEL_PORT)
        )

        ### Vector Store Configuration
        self.VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "Chroma")
        self.MILVUS_URL = os.getenv("MILVUS_URL", "127.0.0.1")
        self.MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
        self.MILVUS_USERNAME = os.getenv("MILVUS_USERNAME", None)
        self.MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", None)

        # QLoRA
        self.QLoRA = os.getenv("QUANTIZE_QLORA", "True")
        self.IS_LOAD_8BIT = os.getenv("QUANTIZE_8bit", "True").lower() == "true"
        self.IS_LOAD_4BIT = os.getenv("QUANTIZE_4bit", "False").lower() == "true"
        if self.IS_LOAD_8BIT and self.IS_LOAD_4BIT:
            self.IS_LOAD_8BIT = False
        # In order to be compatible with the new and old model parameter design
        os.environ["load_8bit"] = str(self.IS_LOAD_8BIT)
        os.environ["load_4bit"] = str(self.IS_LOAD_4BIT)

        ### EMBEDDING Configuration
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text2vec")
        self.KNOWLEDGE_CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", 100))
        self.KNOWLEDGE_CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", 50))
        self.KNOWLEDGE_SEARCH_TOP_SIZE = int(os.getenv("KNOWLEDGE_SEARCH_TOP_SIZE", 5))
        self.KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD = int(
            os.getenv("KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD", 10)
        )
        # default recall similarity score, between 0 and 1
        self.KNOWLEDGE_SEARCH_RECALL_SCORE = float(
            os.getenv("KNOWLEDGE_SEARCH_RECALL_SCORE", 0.3)
        )
        self.KNOWLEDGE_SEARCH_MAX_TOKEN = int(
            os.getenv("KNOWLEDGE_SEARCH_MAX_TOKEN", 2000)
        )
        # Whether to enable Chat Knowledge Search Rewrite Mode
        self.KNOWLEDGE_SEARCH_REWRITE = (
            os.getenv("KNOWLEDGE_SEARCH_REWRITE", "False").lower() == "true"
        )
        # Control whether to display the source document of knowledge on the front end.
        self.KNOWLEDGE_CHAT_SHOW_RELATIONS = (
            os.getenv("KNOWLEDGE_CHAT_SHOW_RELATIONS", "False").lower() == "true"
        )

        ### SUMMARY_CONFIG Configuration
        self.SUMMARY_CONFIG = os.getenv("SUMMARY_CONFIG", "FAST")

        self.MAX_GPU_MEMORY = os.getenv("MAX_GPU_MEMORY", None)

        ### Log level
        self.DBGPT_LOG_LEVEL = os.getenv("DBGPT_LOG_LEVEL", "INFO")

        self.SYSTEM_APP: Optional["SystemApp"] = None

        ### Temporary configuration
        self.USE_FASTCHAT: bool = os.getenv("USE_FASTCHAT", "True").lower() == "true"

        self.MODEL_CACHE_ENABLE: bool = (
            os.getenv("MODEL_CACHE_ENABLE", "True").lower() == "true"
        )
        self.MODEL_CACHE_STORAGE_TYPE: str = os.getenv(
            "MODEL_CACHE_STORAGE_TYPE", "disk"
        )
        self.MODEL_CACHE_MAX_MEMORY_MB: int = int(
            os.getenv("MODEL_CACHE_MAX_MEMORY_MB", 256)
        )
        self.MODEL_CACHE_STORAGE_DISK_DIR: Optional[str] = os.getenv(
            "MODEL_CACHE_STORAGE_DISK_DIR"
        )
        # global dbgpt api key
        self.API_KEYS = os.getenv("API_KEYS", None)

    @property
    def local_db_manager(self) -> "ConnectorManager":
        from dbgpt.datasource.manages import ConnectorManager

        if not self.SYSTEM_APP:
            raise ValueError("SYSTEM_APP is not set")
        return ConnectorManager.get_instance(self.SYSTEM_APP)
