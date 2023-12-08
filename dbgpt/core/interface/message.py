from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Union
from datetime import datetime

from dbgpt._private.pydantic import BaseModel, Field


class BaseMessage(BaseModel, ABC):
    """Message object."""

    content: str
    additional_kwargs: dict = Field(default_factory=dict)

    @property
    @abstractmethod
    def type(self) -> str:
        """Type of the message, used for serialization."""


class HumanMessage(BaseMessage):
    """Type of message that is spoken by the human."""

    example: bool = False

    @property
    def type(self) -> str:
        """Type of the message, used for serialization."""
        return "human"


class AIMessage(BaseMessage):
    """Type of message that is spoken by the AI."""

    example: bool = False

    @property
    def type(self) -> str:
        """Type of the message, used for serialization."""
        return "ai"


class ViewMessage(BaseMessage):
    """Type of message that is spoken by the AI."""

    example: bool = False

    @property
    def type(self) -> str:
        """Type of the message, used for serialization."""
        return "view"


class SystemMessage(BaseMessage):
    """Type of message that is a system message."""

    @property
    def type(self) -> str:
        """Type of the message, used for serialization."""
        return "system"


class ModelMessageRoleType:
    """ "Type of ModelMessage role"""

    SYSTEM = "system"
    HUMAN = "human"
    AI = "ai"
    VIEW = "view"


class ModelMessage(BaseModel):
    """Type of message that interaction between dbgpt-server and llm-server"""

    """Similar to openai's message format"""
    role: str
    content: str

    @staticmethod
    def from_openai_messages(
        messages: Union[str, List[Dict[str, str]]]
    ) -> List["ModelMessage"]:
        """Openai message format to current ModelMessage format"""
        if isinstance(messages, str):
            return [ModelMessage(role=ModelMessageRoleType.HUMAN, content=messages)]
        result = []
        for message in messages:
            msg_role = message["role"]
            content = message["content"]
            if msg_role == "system":
                result.append(
                    ModelMessage(role=ModelMessageRoleType.SYSTEM, content=content)
                )
            elif msg_role == "user":
                result.append(
                    ModelMessage(role=ModelMessageRoleType.HUMAN, content=content)
                )
            elif msg_role == "assistant":
                result.append(
                    ModelMessage(role=ModelMessageRoleType.AI, content=content)
                )
            else:
                raise ValueError(f"Unknown role: {msg_role}")
        return result

    @staticmethod
    def to_openai_messages(messages: List["ModelMessage"]) -> List[Dict[str, str]]:
        """Convert to OpenAI message format and
        hugggingface [Templates of Chat Models](https://huggingface.co/docs/transformers/v4.34.1/en/chat_templating)
        """
        history = []
        # Add history conversation
        for message in messages:
            if message.role == ModelMessageRoleType.HUMAN:
                history.append({"role": "user", "content": message.content})
            elif message.role == ModelMessageRoleType.SYSTEM:
                history.append({"role": "system", "content": message.content})
            elif message.role == ModelMessageRoleType.AI:
                history.append({"role": "assistant", "content": message.content})
            else:
                pass
        # Move the last user's information to the end
        temp_his = history[::-1]
        last_user_input = None
        for m in temp_his:
            if m["role"] == "user":
                last_user_input = m
                break
        if last_user_input:
            history.remove(last_user_input)
            history.append(last_user_input)
        return history

    @staticmethod
    def to_dict_list(messages: List["ModelMessage"]) -> List[Dict[str, str]]:
        return list(map(lambda m: m.dict(), messages))

    @staticmethod
    def build_human_message(content: str) -> "ModelMessage":
        return ModelMessage(role=ModelMessageRoleType.HUMAN, content=content)


def _message_to_dict(message: BaseMessage) -> dict:
    return {"type": message.type, "data": message.dict()}


def _messages_to_dict(messages: List[BaseMessage]) -> List[dict]:
    return [_message_to_dict(m) for m in messages]


def _message_from_dict(message: dict) -> BaseMessage:
    _type = message["type"]
    if _type == "human":
        return HumanMessage(**message["data"])
    elif _type == "ai":
        return AIMessage(**message["data"])
    elif _type == "system":
        return SystemMessage(**message["data"])
    elif _type == "view":
        return ViewMessage(**message["data"])
    else:
        raise ValueError(f"Got unexpected type: {_type}")


def _messages_from_dict(messages: List[dict]) -> List[BaseMessage]:
    return [_message_from_dict(m) for m in messages]


def _parse_model_messages(
    messages: List[ModelMessage],
) -> Tuple[str, List[str], List[List[str, str]]]:
    """
    Parameters:
        messages: List of message from base chat.
    Returns:
        A tuple contains user prompt, system message list and history message list
        str: user prompt
        List[str]: system messages
        List[List[str]]: history message of user and assistant
    """
    user_prompt = ""
    system_messages: List[str] = []
    history_messages: List[List[str]] = [[]]

    for message in messages[:-1]:
        if message.role == "human":
            history_messages[-1].append(message.content)
        elif message.role == "system":
            system_messages.append(message.content)
        elif message.role == "ai":
            history_messages[-1].append(message.content)
            history_messages.append([])
    if messages[-1].role != "human":
        raise ValueError("Hi! What do you want to talk about？")
    # Keep message pair of [user message, assistant message]
    history_messages = list(filter(lambda x: len(x) == 2, history_messages))
    user_prompt = messages[-1].content
    return user_prompt, system_messages, history_messages


class OnceConversation:
    """
    All the information of a conversation, the current single service in memory, can expand cache and database support distributed services
    """

    def __init__(self, chat_mode, user_name: str = None, sys_code: str = None):
        self.chat_mode: str = chat_mode
        self.messages: List[BaseMessage] = []
        self.start_date: str = ""
        self.chat_order: int = 0
        self.model_name: str = ""
        self.param_type: str = ""
        self.param_value: str = ""
        self.cost: int = 0
        self.tokens: int = 0
        self.user_name: str = user_name
        self.sys_code: str = sys_code

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
            self.__update_ai_message(message)
        else:
            self.messages.append(AIMessage(content=message))
        """  """

    def __update_ai_message(self, new_message: str) -> None:
        """
        stream out message update
        Args:
            new_message:

        Returns:

        """

        for item in self.messages:
            if item.type == "ai":
                item.content = new_message

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

    def get_user_conv(self):
        for message in self.messages:
            if isinstance(message, HumanMessage):
                return message
        return None

    def get_system_conv(self):
        system_convs = []
        for message in self.messages:
            if isinstance(message, SystemMessage):
                system_convs.append(message)
        return system_convs


def _conversation_to_dict(once: OnceConversation) -> dict:
    start_str: str = ""
    if hasattr(once, "start_date") and once.start_date:
        if isinstance(once.start_date, datetime):
            start_str = once.start_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_str = once.start_date

    return {
        "chat_mode": once.chat_mode,
        "model_name": once.model_name,
        "chat_order": once.chat_order,
        "start_date": start_str,
        "cost": once.cost if once.cost else 0,
        "tokens": once.tokens if once.tokens else 0,
        "messages": _messages_to_dict(once.messages),
        "param_type": once.param_type,
        "param_value": once.param_value,
        "user_name": once.user_name,
        "sys_code": once.sys_code,
    }


def _conversations_to_dict(conversations: List[OnceConversation]) -> List[dict]:
    return [_conversation_to_dict(m) for m in conversations]


def _conversation_from_dict(once: dict) -> OnceConversation:
    conversation = OnceConversation(
        once.get("chat_mode"), once.get("user_name"), once.get("sys_code")
    )
    conversation.cost = once.get("cost", 0)
    conversation.chat_mode = once.get("chat_mode", "chat_normal")
    conversation.tokens = once.get("tokens", 0)
    conversation.start_date = once.get("start_date", "")
    conversation.chat_order = int(once.get("chat_order"))
    conversation.param_type = once.get("param_type", "")
    conversation.param_value = once.get("param_value", "")
    conversation.model_name = once.get("model_name", "proxyllm")
    print(once.get("messages"))
    conversation.messages = _messages_from_dict(once.get("messages", []))
    return conversation
