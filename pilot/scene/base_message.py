from __future__ import annotations

from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Tuple,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from pydantic import BaseModel, Extra, Field, root_validator


class PromptValue(BaseModel, ABC):
    @abstractmethod
    def to_string(self) -> str:
        """Return prompt as string."""

    @abstractmethod
    def to_messages(self) -> List[BaseMessage]:
        """Return prompt as messages."""


class BaseMessage(BaseModel):
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


class ModelMessage(BaseModel):
    """Type of message that interaction between dbgpt-server and llm-server"""

    """Similar to openai's message format"""
    role: str
    content: str


class ModelMessageRoleType:
    """ "Type of ModelMessage role"""

    SYSTEM = "system"
    HUMAN = "human"
    AI = "ai"


class Generation(BaseModel):
    """Output of a single generation."""

    text: str
    """Generated text output."""

    generation_info: Optional[Dict[str, Any]] = None
    """Raw generation info response from the provider"""
    """May include things like reason for finishing (e.g. in OpenAI)"""


class ChatGeneration(Generation):
    """Output of a single generation."""

    text = ""
    message: BaseMessage

    @root_validator
    def set_text(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values["text"] = values["message"].content
        return values


class ChatResult(BaseModel):
    """Class that contains all relevant information for a Chat Result."""

    generations: List[ChatGeneration]
    """List of the things generated."""
    llm_output: Optional[dict] = None
    """For arbitrary LLM provider specific output."""


class LLMResult(BaseModel):
    """Class that contains all relevant information for an LLM Result."""

    generations: List[List[Generation]]
    """List of the things generated. This is List[List[]] because
    each input could have multiple generations."""
    llm_output: Optional[dict] = None
    """For arbitrary LLM provider specific output."""


def _message_to_dict(message: BaseMessage) -> dict:
    return {"type": message.type, "data": message.dict()}


def messages_to_dict(messages: List[BaseMessage]) -> List[dict]:
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


def messages_from_dict(messages: List[dict]) -> List[BaseMessage]:
    return [_message_from_dict(m) for m in messages]


def _parse_model_messages(
    messages: List[ModelMessage],
) -> Tuple[str, List[str], List[List[str, str]]]:
    """ "
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
