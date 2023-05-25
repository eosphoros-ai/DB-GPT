from __future__ import annotations
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, root_validator, validator
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
)

from pilot.scene.base_message import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    ViewMessage,
    messages_to_dict,
    messages_from_dict,
)


class OnceConversation:
    """
    All the information of a conversation, the current single service in memory, can expand cache and database support distributed services
    """

    def __init__(self):
        self.messages: List[BaseMessage] = []
        self.start_date: str = ""
        self.chat_order: int = 0
        self.cost: int = 0
        self.tokens: int = 0

    def add_user_message(self, message: str) -> None:
        """Add a user message to the store"""
        has_message = any(
            isinstance(instance, HumanMessage) for instance in self.messages
        )
        if has_message:
            raise ValueError("Already Have Human message")
        self.messages.append(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        """Add an AI message to the store"""
        has_message = any(isinstance(instance, AIMessage) for instance in self.messages)
        if has_message:
            raise ValueError("Already Have Ai message")
        self.messages.append(AIMessage(content=message))
        """  """

    def add_view_message(self, message: str) -> None:
        """Add an AI message to the store"""

        self.messages.append(ViewMessage(content=message))
        """  """

    def add_system_message(self, message: str) -> None:
        """Add an AI message to the store"""
        self.messages.append(SystemMessage(content=message))

    def set_start_time(self, datatime: datetime):
        dt_str = datatime.strftime("%Y-%m-%d %H:%M:%S")
        self.start_date = dt_str

    def clear(self) -> None:
        """Remove all messages from the store"""
        self.messages.clear()
        self.session_id = None


def _conversation_to_dic(once: OnceConversation) -> dict:
    start_str: str = ""
    if once.start_date:
        if isinstance(once.start_date, datetime):
            start_str = once.start_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_str = once.start_date

    return {
        "chat_order": once.chat_order,
        "start_date": start_str,
        "cost": once.cost if once.cost else 0,
        "tokens": once.tokens if once.tokens else 0,
        "messages": messages_to_dict(once.messages),
    }


def conversations_to_dict(conversations: List[OnceConversation]) -> List[dict]:
    return [_conversation_to_dic(m) for m in conversations]


def conversation_from_dict(once: dict) -> OnceConversation:
    conversation = OnceConversation()
    conversation.cost = once.get("cost", 0)
    conversation.tokens = once.get("tokens", 0)
    conversation.start_date = once.get("start_date", "")
    conversation.chat_order = int(once.get("chat_order"))
    print(once.get("messages"))
    conversation.messages = messages_from_dict(once.get("messages", []))
    return conversation
