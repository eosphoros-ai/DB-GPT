from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional, Union

from pydantic import BaseModel, Field, root_validator


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
