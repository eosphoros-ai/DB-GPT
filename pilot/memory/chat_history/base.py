from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from enum import Enum
from pilot.scene.message import OnceConversation


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
    def append(self, once_message: OnceConversation, user_id: str = None) -> None:
        """Append the message to the record in the local file"""

    # @abstractmethod
    # def clear(self) -> None:
    #     """Clear session memory from the local file"""

    @abstractmethod
    def conv_list(self, user_name: str = None) -> None:
        """get user's conversation list"""
        pass

    @abstractmethod
    def update(self, messages: List[OnceConversation]) -> None:
        pass

    @abstractmethod
    def delete(self) -> bool:
        pass

    @abstractmethod
    def conv_info(self, conv_uid: str = None) -> None:
        pass

    @abstractmethod
    def get_messages(self) -> List[OnceConversation]:
        pass

    @staticmethod
    def conv_list(cls, user_name: str = None) -> None:
        pass
