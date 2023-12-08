from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from enum import Enum
from dbgpt.core.interface.message import OnceConversation


class MemoryStoreType(Enum):
    File = "file"
    Memory = "memory"
    DB = "db"
    DuckDb = "duckdb"


class BaseChatHistoryMemory(ABC):
    store_type: MemoryStoreType

    def __init__(self):
        self.conversations: List[OnceConversation] = []

    @abstractmethod
    def messages(self) -> List[OnceConversation]:  # type: ignore
        """Retrieve the messages from the local file"""

    @abstractmethod
    def create(self, user_name: str) -> None:
        """Append the message to the record in the local file"""

    @abstractmethod
    def append(self, message: OnceConversation) -> None:
        """Append the message to the record in the local file"""

    # @abstractmethod
    # def clear(self) -> None:
    #     """Clear session memory from the local file"""

    @abstractmethod
    def update(self, messages: List[OnceConversation]) -> None:
        pass

    @abstractmethod
    def delete(self) -> bool:
        pass

    @abstractmethod
    def conv_info(self, conv_uid: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def get_messages(self) -> List[OnceConversation]:
        pass

    @staticmethod
    def conv_list(
        user_name: Optional[str] = None, sys_code: Optional[str] = None
    ) -> List[Dict]:
        """get user's conversation list"""
