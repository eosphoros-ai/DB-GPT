from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, root_validator, validator, Extra
from typing import (
    Any,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)
import requests
from urllib.parse import urljoin

import pilot.configs.config
from pilot.scene.message import OnceConversation
from pilot.prompts.prompt_new import PromptTemplate
from pilot.memory.chat_history.base import BaseChatHistoryMemory
from pilot.memory.chat_history.file_history import FileHistoryMemory

from pilot.configs.model_config import LOGDIR, DATASETS_DIR
from pilot.utils import (
    build_logger,
    server_error_msg,
)
from pilot.common.schema import SeparatorStyle
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

logger = build_logger("BaseChat", LOGDIR + "BaseChat.log")
headers = {"User-Agent": "dbgpt Client"}
CFG = Config()


class BaseChat(ABC):
    chat_scene: str = None
    llm_model: Any = None
    temperature: float = 0.6
    max_new_tokens: int = 1024
    # By default, keep the last two rounds of conversation records as the context
    chat_retention_rounds: int = 2

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    def __init__(self, chat_mode, chat_session_id, current_user_input):
        self.chat_session_id = chat_session_id
        self.chat_mode = chat_mode
        self.current_user_input: str = current_user_input
        self.llm_model = CFG.LLM_MODEL
        ### TODO
        self.memory = FileHistoryMemory(chat_session_id)
        ### load prompt template
        self.prompt_template: PromptTemplate = CFG.prompt_templates[
            self.chat_mode.value
        ]
        self.history_message: List[OnceConversation] = []
        self.current_message: OnceConversation = OnceConversation()
        self.current_tokens_used: int = 0
        ### load chat_session_id's chat historys
        self._load_history(self.chat_session_id)

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def chat_type(self) -> str:
        raise NotImplementedError("Not supported for this chat type.")

    def call(self):
        pass

    def chat_show(self):
        pass

    def current_ai_response(self) -> str:
        pass

    def _load_history(self, session_id: str) -> List[OnceConversation]:
        """
        load chat history by session_id
        Args:
            session_id:
        Returns:
        """
        return self.memory.messages()

    def generate(self, p) -> str:
        """
        generate context for LLM input
        Args:
            p:

        Returns:

        """
        pass
