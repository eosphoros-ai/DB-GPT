from __future__ import annotations

from pydantic import BaseModel, Field, root_validator, validator, Extra
from abc import ABC, abstractmethod
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

from pilot.scene.message import OnceConversation


class BaseChatHistoryMemory(ABC):
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

    @abstractmethod
    def clear(self) -> None:
        """Clear session memory from the local file"""

    def conv_list(self, user_name: str = None) -> None:
        """get user's conversation list"""
        pass
