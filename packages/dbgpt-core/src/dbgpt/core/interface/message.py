"""The conversation and message module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple, Union, cast

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.core.interface.storage import (
    InMemoryStorage,
    ResourceIdentifier,
    StorageInterface,
    StorageItem,
)


class BaseMessage(BaseModel, ABC):
    """Message object."""

    content: str
    index: int = 0
    round_index: int = 0
    """The round index of the message in the conversation"""
    additional_kwargs: dict = Field(default_factory=dict)

    @property
    @abstractmethod
    def type(self) -> str:
        """Type of the message, used for serialization."""

    @property
    def pass_to_model(self) -> bool:
        """Whether the message will be passed to the model."""
        return True

    def to_dict(self) -> Dict:
        """Convert to dict.

        Returns:
            Dict: The dict object
        """
        return {
            "type": self.type,
            "data": model_to_dict(self),
            "index": self.index,
            "round_index": self.round_index,
        }

    @staticmethod
    def messages_to_string(messages: List["BaseMessage"]) -> str:
        """Convert messages to str.

        Args:
            messages (List[BaseMessage]): The messages

        Returns:
            str: The str messages
        """
        return _messages_to_str(messages)


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

    @property
    def pass_to_model(self) -> bool:
        """Whether the message will be passed to the model.

        The view message will not be passed to the model
        """
        return False


class SystemMessage(BaseMessage):
    """Type of message that is a system message."""

    @property
    def type(self) -> str:
        """Type of the message, used for serialization."""
        return "system"


class ModelMessageRoleType:
    """Type of ModelMessage role."""

    SYSTEM = "system"
    HUMAN = "human"
    AI = "ai"
    VIEW = "view"


class ModelMessage(BaseModel):
    """Type of message that interaction between dbgpt-server and llm-server."""

    """Similar to openai's message format"""
    role: str
    content: str
    round_index: Optional[int] = 0

    @property
    def pass_to_model(self) -> bool:
        """Whether the message will be passed to the model.

        The view message will not be passed to the model

        Returns:
            bool: Whether the message will be passed to the model
        """
        return self.role in [
            ModelMessageRoleType.SYSTEM,
            ModelMessageRoleType.HUMAN,
            ModelMessageRoleType.AI,
        ]

    @staticmethod
    def from_base_messages(messages: List[BaseMessage]) -> List["ModelMessage"]:
        """Covert BaseMessage format to current ModelMessage format.

        Args:
            messages (List[BaseMessage]): The base messages

        Returns:
            List[ModelMessage]: The model messages
        """
        result = []
        for message in messages:
            content, round_index = message.content, message.round_index
            if isinstance(message, HumanMessage):
                result.append(
                    ModelMessage(
                        role=ModelMessageRoleType.HUMAN,
                        content=content,
                        round_index=round_index,
                    )
                )
            elif isinstance(message, AIMessage):
                result.append(
                    ModelMessage(
                        role=ModelMessageRoleType.AI,
                        content=content,
                        round_index=round_index,
                    )
                )
            elif isinstance(message, SystemMessage):
                result.append(
                    ModelMessage(
                        role=ModelMessageRoleType.SYSTEM, content=message.content
                    )
                )
        return result

    @staticmethod
    def from_openai_messages(
        messages: Union[str, List[Dict[str, str]]],
    ) -> List["ModelMessage"]:
        """Openai message format to current ModelMessage format."""
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
    def to_common_messages(
        messages: List["ModelMessage"],
        convert_to_compatible_format: bool = False,
        support_system_role: bool = True,
    ) -> List[Dict[str, str]]:
        """Cover to common message format.

        Convert to common message format(e.g. OpenAI message format) and
        huggingface [Templates of Chat Models]
        (https://huggingface.co/docs/transformers/v4.34.1/en/chat_templating)

        Args:
            messages (List["ModelMessage"]): The model messages
            convert_to_compatible_format (bool): Whether to convert to compatible format
            support_system_role (bool): Whether to support system role

        Returns:
            List[Dict[str, str]]: The common messages

        Raises:
            ValueError: If the message role is not supported
        """
        history = []
        # Add history conversation
        for message in messages:
            if message.role == ModelMessageRoleType.HUMAN:
                history.append({"role": "user", "content": message.content})
            elif message.role == ModelMessageRoleType.SYSTEM:
                if not support_system_role:
                    raise ValueError("Current model not support system role")
                history.append({"role": "system", "content": message.content})
            elif message.role == ModelMessageRoleType.AI:
                history.append({"role": "assistant", "content": message.content})
            else:
                pass
        if convert_to_compatible_format:
            # Move the last user's information to the end
            last_user_input_index = None
            for i in range(len(history) - 1, -1, -1):
                if history[i]["role"] == "user":
                    last_user_input_index = i
                    break
            if last_user_input_index:
                last_user_input = history.pop(last_user_input_index)
                history.append(last_user_input)
        return history

    @staticmethod
    def to_dict_list(messages: List["ModelMessage"]) -> List[Dict[str, str]]:
        """Convert to dict list.

        Args:
            messages (List["ModelMessage"]): The model messages

        Returns:
            List[Dict[str, str]]: The dict list
        """
        return list(map(lambda m: model_to_dict(m), messages))

    @staticmethod
    def build_human_message(content: str) -> "ModelMessage":
        """Build human message.

        Args:
            content (str): The content

        Returns:
            ModelMessage: The model message
        """
        return ModelMessage(role=ModelMessageRoleType.HUMAN, content=content)

    @staticmethod
    def get_printable_message(messages: List["ModelMessage"]) -> str:
        """Get the printable message.

        Args:
            messages (List["ModelMessage"]): The model messages

        Returns:
            str: The printable message
        """
        str_msg = ""
        for message in messages:
            curr_message = (
                f"(Round {message.round_index}) {message.role}: {message.content} "
            )
            str_msg += curr_message.rstrip() + "\n"

        return str_msg

    @staticmethod
    def messages_to_string(
        messages: List["ModelMessage"],
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
        system_prefix: str = "System",
    ) -> str:
        """Convert messages to str.

        Args:
            messages (List[ModelMessage]): The messages
            human_prefix (str): The human prefix
            ai_prefix (str): The ai prefix
            system_prefix (str): The system prefix

        Returns:
            str: The str messages
        """
        return _messages_to_str(messages, human_prefix, ai_prefix, system_prefix)

    @staticmethod
    def parse_user_message(messages: List[ModelMessage]) -> str:
        """Parse user message from messages.

        Args:
            messages (List[ModelMessage]): The all messages in the conversation.

        Returns:
            str: The user message
        """
        lass_user_message = None
        for message in messages[::-1]:
            if message.role == ModelMessageRoleType.HUMAN:
                lass_user_message = message.content
                break
        if not lass_user_message:
            raise ValueError("No user message")
        return lass_user_message


_SingleRoundMessage = List[BaseMessage]
_MultiRoundMessageMapper = Callable[[List[_SingleRoundMessage]], List[BaseMessage]]


def _message_to_dict(message: BaseMessage) -> Dict:
    return message.to_dict()


def _messages_to_dict(messages: List[BaseMessage]) -> List[Dict]:
    return [_message_to_dict(m) for m in messages]


def _messages_to_str(
    messages: Union[List[BaseMessage], List[ModelMessage]],
    human_prefix: str = "Human",
    ai_prefix: str = "AI",
    system_prefix: str = "System",
) -> str:
    """Convert messages to str.

    Args:
        messages (List[Union[BaseMessage, ModelMessage]]): The messages
        human_prefix (str): The human prefix
        ai_prefix (str): The ai prefix
        system_prefix (str): The system prefix

    Returns:
        str: The str messages
    """
    str_messages = []
    for message in messages:
        role = None
        if isinstance(message, HumanMessage):
            role = human_prefix
        elif isinstance(message, AIMessage):
            role = ai_prefix
        elif isinstance(message, SystemMessage):
            role = system_prefix
        elif isinstance(message, ViewMessage):
            pass
        elif isinstance(message, ModelMessage):
            role = message.role
        else:
            raise ValueError(f"Got unsupported message type: {message}")
        if role:
            str_messages.append(f"{role}: {message.content}")
    return "\n".join(str_messages)


def _message_from_dict(message: Dict) -> BaseMessage:
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


def _messages_from_dict(messages: List[Dict]) -> List[BaseMessage]:
    return [_message_from_dict(m) for m in messages]


def parse_model_messages(
    messages: List[ModelMessage],
) -> Tuple[str, List[str], List[List[str]]]:
    """Parse model messages.

    Parse model messages to extract the user prompt, system messages, and a history of
    conversation.

    This function analyzes a list of ModelMessage objects, identifying the role of each
     message (e.g., human, system, ai)
    and categorizes them accordingly. The last message is expected to be from the user
    (human), and it's treated as
    the current user prompt. System messages are extracted separately, and the
    conversation history is compiled into pairs of human and AI messages.

    Args:
        messages (List[ModelMessage]): List of messages from a chat conversation.

    Returns:
        tuple: A tuple containing the user prompt, list of system messages, and the
            conversation history.
            The conversation history is a list of message pairs, each containing a
            user message and the corresponding AI response.

    Examples:
        .. code-block:: python

            # Example 1: Single round of conversation
            messages = [
                ModelMessage(role="human", content="Hello"),
                ModelMessage(role="ai", content="Hi there!"),
                ModelMessage(role="human", content="How are you?"),
            ]
            user_prompt, system_messages, history = parse_model_messages(messages)
            # user_prompt: "How are you?"
            # system_messages: []
            # history: [["Hello", "Hi there!"]]

            # Example 2: Conversation with system messages
            messages = [
                ModelMessage(role="system", content="System initializing..."),
                ModelMessage(role="human", content="Is it sunny today?"),
                ModelMessage(role="ai", content="Yes, it's sunny."),
                ModelMessage(role="human", content="Great!"),
            ]
            user_prompt, system_messages, history = parse_model_messages(messages)
            # user_prompt: "Great!"
            # system_messages: ["System initializing..."]
            # history: [["Is it sunny today?", "Yes, it's sunny."]]

            # Example 3: Multiple rounds with system message
            messages = [
                ModelMessage(role="human", content="Hi"),
                ModelMessage(role="ai", content="Hello!"),
                ModelMessage(role="system", content="Error 404"),
                ModelMessage(role="human", content="What's the error?"),
                ModelMessage(role="ai", content="Just a joke."),
                ModelMessage(role="human", content="Funny!"),
            ]
            user_prompt, system_messages, history = parse_model_messages(messages)
            # user_prompt: "Funny!"
            # system_messages: ["Error 404"]
            # history: [["Hi", "Hello!"], ["What's the error?", "Just a joke."]]
    """
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
    # Keep message a pair of [user message, assistant message]
    history_messages = list(filter(lambda x: len(x) == 2, history_messages))
    user_prompt = messages[-1].content
    return user_prompt, system_messages, history_messages


class OnceConversation:
    """Once conversation.

    All the information of a conversation, the current single service in memory,
    can expand cache and database support distributed services.
    """

    def __init__(
        self,
        chat_mode: str,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        summary: Optional[str] = None,
        app_code: Optional[str] = None,
        **kwargs,
    ):
        """Create a new conversation."""
        self.chat_mode: str = chat_mode
        self.user_name: Optional[str] = user_name
        self.sys_code: Optional[str] = sys_code
        self.summary: Optional[str] = summary
        self.app_code: Optional[str] = app_code

        self.messages: List[BaseMessage] = kwargs.get("messages", [])
        self.start_date: str = kwargs.get("start_date", "")
        # After each complete round of dialogue, the current value will be
        # increased by 1
        self.chat_order: int = int(kwargs.get("chat_order", 0))
        self.model_name: str = kwargs.get("model_name", "")
        self.param_type: str = kwargs.get("param_type", "")
        self.param_value: str = kwargs.get("param_value", "")
        self.cost: int = int(kwargs.get("cost", 0))
        self.tokens: int = int(kwargs.get("tokens", 0))
        self._message_index: int = int(kwargs.get("message_index", 0))

    def _append_message(self, message: BaseMessage) -> None:
        index = self._message_index
        self._message_index += 1
        message.index = index
        message.round_index = self.chat_order
        message.additional_kwargs["param_type"] = self.param_type
        message.additional_kwargs["param_value"] = self.param_value
        message.additional_kwargs["model_name"] = self.model_name
        self.messages.append(message)

    def start_new_round(self) -> None:
        """Start a new round of conversation.

        Example:
            >>> conversation = OnceConversation("chat_normal")
            >>> # The chat order will be 0, then we start a new round of conversation
            >>> assert conversation.chat_order == 0
            >>> conversation.start_new_round()
            >>> # Now the chat order will be 1
            >>> assert conversation.chat_order == 1
            >>> conversation.add_user_message("hello")
            >>> conversation.add_ai_message("hi")
            >>> conversation.end_current_round()
            >>> # Now the chat order will be 1, then we start a new round of
            >>> # conversation
            >>> conversation.start_new_round()
            >>> # Now the chat order will be 2
            >>> assert conversation.chat_order == 2
            >>> conversation.add_user_message("hello")
            >>> conversation.add_ai_message("hi")
            >>> conversation.end_current_round()
            >>> assert conversation.chat_order == 2
        """
        self.chat_order += 1

    def end_current_round(self) -> None:
        """Execute the end of the current round of conversation.

        We do noting here, just for the interface
        """
        pass

    def add_user_message(
        self, message: str, check_duplicate_type: Optional[bool] = False
    ) -> None:
        """Save a user message to the conversation.

        Args:
            message (str): The message content
            check_duplicate_type (bool): Whether to check the duplicate message type

        Raises:
            ValueError: If the message is duplicate and check_duplicate_type is True
        """
        if check_duplicate_type:
            has_message = any(
                isinstance(instance, HumanMessage) for instance in self.messages
            )
            if has_message:
                raise ValueError("Already Have Human message")
        self._append_message(HumanMessage(content=message))

    def add_ai_message(
        self, message: str, update_if_exist: Optional[bool] = False
    ) -> None:
        """Save an AI message to current conversation.

        Args:
            message (str): The message content
            update_if_exist (bool): Whether to update the message if the message type
                is duplicate
        """
        if not update_if_exist:
            self._append_message(AIMessage(content=message))
            return
        has_message = any(isinstance(instance, AIMessage) for instance in self.messages)
        if has_message:
            self._update_ai_message(message)
        else:
            self._append_message(AIMessage(content=message))

    def _update_ai_message(self, new_message: str) -> None:
        """Update the all AI message to new message.

        stream out message update

        Args:
            new_message (str): The new message
        """
        for item in self.messages:
            if item.type == "ai":
                item.content = new_message

    def add_view_message(self, message: str) -> None:
        """Save a view message to current conversation."""
        self._append_message(ViewMessage(content=message))

    def add_system_message(self, message: str) -> None:
        """Save a system message to current conversation."""
        self._append_message(SystemMessage(content=message))

    def set_start_time(self, datatime: datetime):
        """Set the start time of the conversation."""
        dt_str = datatime.strftime("%Y-%m-%d %H:%M:%S")
        self.start_date = dt_str

    def clear(self) -> None:
        """Remove all messages from the store."""
        self.messages.clear()

    def get_latest_user_message(self) -> Optional[HumanMessage]:
        """Get the latest user message."""
        for message in self.messages[::-1]:
            if isinstance(message, HumanMessage):
                return message
        return None

    def get_system_messages(self) -> List[SystemMessage]:
        """Get the latest user message.

        Returns:
            List[SystemMessage]: The system messages
        """
        return cast(
            List[SystemMessage],
            list(filter(lambda x: isinstance(x, SystemMessage), self.messages)),
        )

    def _to_dict(self) -> Dict:
        return _conversation_to_dict(self)

    def from_conversation(self, conversation: OnceConversation) -> None:
        """Load the conversation from the storage."""
        self.chat_mode = conversation.chat_mode
        self.messages = conversation.messages
        self.start_date = conversation.start_date
        self.chat_order = conversation.chat_order
        if not self.model_name and conversation.model_name:
            self.model_name = conversation.model_name
        if not self.app_code and conversation.app_code:
            self.app_code = conversation.app_code
        if not self.param_type and conversation.param_type:
            self.param_type = conversation.param_type
        if not self.param_value and conversation.param_value:
            self.param_value = conversation.param_value
        self.cost = conversation.cost
        self.tokens = conversation.tokens
        self.user_name = conversation.user_name
        self.sys_code = conversation.sys_code
        self._message_index = conversation._message_index

    def get_messages_by_round(self, round_index: int) -> List[BaseMessage]:
        """Get the messages by round index.

        Args:
            round_index (int): The round index

        Returns:
            List[BaseMessage]: The messages
        """
        return list(filter(lambda x: x.round_index == round_index, self.messages))

    def get_latest_round(self) -> List[BaseMessage]:
        """Get the latest round messages.

        Returns:
            List[BaseMessage]: The messages
        """
        return self.get_messages_by_round(self.chat_order)

    def get_messages_with_round(self, round_count: int) -> List[BaseMessage]:
        """Get the messages with round count.

        If the round count is 1, the history messages will not be included.

        Example:
            .. code-block:: python

                conversation = OnceConversation()
                conversation.start_new_round()
                conversation.add_user_message("hello, this is the first round")
                conversation.add_ai_message("hi")
                conversation.end_current_round()
                conversation.start_new_round()
                conversation.add_user_message("hello, this is the second round")
                conversation.add_ai_message("hi")
                conversation.end_current_round()
                conversation.start_new_round()
                conversation.add_user_message("hello, this is the third round")
                conversation.add_ai_message("hi")
                conversation.end_current_round()

                assert len(conversation.get_messages_with_round(1)) == 2
                assert (
                    conversation.get_messages_with_round(1)[0].content
                    == "hello, this is the third round"
                )
                assert conversation.get_messages_with_round(1)[1].content == "hi"

                assert len(conversation.get_messages_with_round(2)) == 4
                assert (
                    conversation.get_messages_with_round(2)[0].content
                    == "hello, this is the second round"
                )
                assert conversation.get_messages_with_round(2)[1].content == "hi"

        Args:
            round_count (int): The round count

        Returns:
            List[BaseMessage]: The messages
        """
        latest_round_index = self.chat_order
        start_round_index = max(1, latest_round_index - round_count + 1)
        messages = []
        for round_index in range(start_round_index, latest_round_index + 1):
            messages.extend(self.get_messages_by_round(round_index))
        return messages

    def get_model_messages(self) -> List[ModelMessage]:
        """Get the model messages.

        Model messages just include human, ai and system messages.
        Model messages maybe include the history messages, The order of the messages is
        the same as the order of
        the messages in the conversation, the last message is the latest message.

        If you want to hand the message with your own logic, you can override this
        method.

        Examples:
            If you not need the history messages, you can override this method
            like this:
            .. code-block:: python

                def get_model_messages(self) -> List[ModelMessage]:
                    messages = []
                    for message in self.get_latest_round():
                        if message.pass_to_model:
                            messages.append(
                                ModelMessage(role=message.type, content=message.content)
                            )
                    return messages

            If you want to add the one round history messages, you can override this
            method like this:
            .. code-block:: python

                def get_model_messages(self) -> List[ModelMessage]:
                    messages = []
                    latest_round_index = self.chat_order
                    round_count = 1
                    start_round_index = max(1, latest_round_index - round_count + 1)
                    for round_index in range(start_round_index, latest_round_index + 1):
                        for message in self.get_messages_by_round(round_index):
                            if message.pass_to_model:
                                messages.append(
                                    ModelMessage(
                                        role=message.type, content=message.content
                                    )
                                )
                    return messages

        Returns:
            List[ModelMessage]: The model messages
        """
        messages = []
        for message in self.messages:
            if message.pass_to_model:
                messages.append(
                    ModelMessage(
                        role=message.type,
                        content=message.content,
                        round_index=message.round_index,
                    )
                )
        return messages

    def get_history_message(
        self, include_system_message: bool = False
    ) -> List[BaseMessage]:
        """Get the history message.

        Not include the system messages.

        Args:
            include_system_message (bool): Whether to include the system message

        Returns:
            List[BaseMessage]: The history messages
        """
        messages = []
        for message in self.messages:
            if (
                message.pass_to_model
                and include_system_message
                or message.type != "system"
            ):
                messages.append(message)
        return messages


class ConversationIdentifier(ResourceIdentifier):
    """Conversation identifier."""

    def __init__(self, conv_uid: str, identifier_type: str = "conversation"):
        """Create a conversation identifier.

        Args:
            conv_uid (str): The conversation uid
            identifier_type (str): The identifier type
        """
        self.conv_uid = conv_uid
        self.identifier_type = identifier_type

    @property
    def str_identifier(self) -> str:
        """Return the str identifier."""
        return f"{self.identifier_type}:{self.conv_uid}"  # noqa:

    def to_dict(self) -> Dict:
        """Convert to dict."""
        return {"conv_uid": self.conv_uid, "identifier_type": self.identifier_type}


class MessageIdentifier(ResourceIdentifier):
    """Message identifier."""

    identifier_split = "___"

    def __init__(self, conv_uid: str, index: int, identifier_type: str = "message"):
        """Create a message identifier."""
        self.conv_uid = conv_uid
        self.index = index
        self.identifier_type = identifier_type

    @property
    def str_identifier(self) -> str:
        """Return the str identifier."""
        return (
            f"{self.identifier_type}{self.identifier_split}{self.conv_uid}"
            f"{self.identifier_split}{self.index}"
        )

    @staticmethod
    def from_str_identifier(str_identifier: str) -> MessageIdentifier:
        """Convert from str identifier.

        Args:
            str_identifier (str): The str identifier

        Returns:
            MessageIdentifier: The message identifier
        """
        parts = str_identifier.split(MessageIdentifier.identifier_split)
        if len(parts) != 3:
            raise ValueError(f"Invalid str identifier: {str_identifier}")
        return MessageIdentifier(parts[1], int(parts[2]))

    def to_dict(self) -> Dict:
        """Convert to dict."""
        return {
            "conv_uid": self.conv_uid,
            "index": self.index,
            "identifier_type": self.identifier_type,
        }


class MessageStorageItem(StorageItem):
    """The message storage item.

    Keep the message detail and the message index.
    """

    @property
    def identifier(self) -> MessageIdentifier:
        """Return the identifier."""
        return self._id

    def __init__(self, conv_uid: str, index: int, message_detail: Dict):
        """Create a message storage item.

        Args:
            conv_uid (str): The conversation uid
            index (int): The message index
            message_detail (Dict): The message detail
        """
        self.conv_uid = conv_uid
        self.index = index
        self.message_detail = message_detail
        self._id = MessageIdentifier(conv_uid, index)

    def to_dict(self) -> Dict:
        """Convert to dict."""
        return {
            "conv_uid": self.conv_uid,
            "index": self.index,
            "message_detail": self.message_detail,
        }

    def to_message(self) -> BaseMessage:
        """Convert to message object.

        Returns:
            BaseMessage: The message object

        Raises:
            ValueError: If the message type is not supported
        """
        return _message_from_dict(self.message_detail)

    def merge(self, other: "StorageItem") -> None:
        """Merge the other message to self.

        Args:
            other (StorageItem): The other message
        """
        if not isinstance(other, MessageStorageItem):
            raise ValueError(f"Can not merge {other} to {self}")
        self.message_detail = other.message_detail


class StorageConversation(OnceConversation, StorageItem):
    """The storage conversation.

    All the information of a conversation, the current single service in memory,
    can expand cache and database support distributed services.

    """

    @property
    def identifier(self) -> ConversationIdentifier:
        """Return the identifier."""
        return self._id

    def to_dict(self) -> Dict:
        """Convert to dict."""
        dict_data = self._to_dict()
        messages: Dict = dict_data.pop("messages")
        message_ids = []
        index = 0
        for message in messages:
            if "index" in message:
                message_idx = message["index"]
            else:
                message_idx = index
                index += 1
            message_ids.append(
                MessageIdentifier(self.conv_uid, message_idx).str_identifier
            )
        # Replace message with message ids
        dict_data["conv_uid"] = self.conv_uid
        dict_data["message_ids"] = message_ids
        dict_data["save_message_independent"] = self.save_message_independent
        return dict_data

    def merge(self, other: "StorageItem") -> None:
        """Merge the other conversation to self.

        Args:
            other (StorageItem): The other conversation
        """
        if not isinstance(other, StorageConversation):
            raise ValueError(f"Can not merge {other} to {self}")
        self.from_conversation(other)

    def __init__(
        self,
        conv_uid: str,
        chat_mode: str = "chat_normal",
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        message_ids: Optional[List[str]] = None,
        summary: Optional[str] = None,
        app_code: Optional[str] = None,
        save_message_independent: bool = True,
        conv_storage: Optional[StorageInterface] = None,
        message_storage: Optional[StorageInterface] = None,
        load_message: bool = True,
        **kwargs,
    ):
        """Create a conversation."""
        super().__init__(chat_mode, user_name, sys_code, summary, app_code, **kwargs)
        self.conv_uid = conv_uid
        self._message_ids = message_ids
        # Record the message index last time saved to the storage,
        # next time save messages which index is _has_stored_message_index + 1
        self._has_stored_message_index = (
            len(kwargs["messages"]) - 1 if "messages" in kwargs else -1
        )
        # Whether to load the message from the storage
        self._load_message = load_message
        self.save_message_independent = save_message_independent
        self._id = ConversationIdentifier(conv_uid)
        if conv_storage is None:
            conv_storage = InMemoryStorage()
        if message_storage is None:
            message_storage = InMemoryStorage()
        self.conv_storage = conv_storage
        self.message_storage = message_storage
        # Load from storage
        self.load_from_storage(self.conv_storage, self.message_storage)

    @property
    def message_ids(self) -> List[str]:
        """Return the message ids.

        Returns:
            List[str]: The message ids
        """
        return self._message_ids if self._message_ids else []

    def end_current_round(self) -> None:
        """End the current round of conversation.

        Save the conversation to the storage after a round of conversation
        """
        self.save_to_storage()

    def _get_message_items(self) -> List[MessageStorageItem]:
        return [
            MessageStorageItem(self.conv_uid, message.index, message.to_dict())
            for message in self.messages
        ]

    def save_to_storage(self) -> None:
        """Save the conversation to the storage."""
        # Save messages first
        message_list = self._get_message_items()
        self._message_ids = [
            message.identifier.str_identifier for message in message_list
        ]
        messages_to_save = message_list[self._has_stored_message_index + 1 :]
        self._has_stored_message_index = len(message_list) - 1
        if self.save_message_independent:
            # Save messages independently
            self.message_storage.save_list(messages_to_save)
        # Save conversation
        if self.summary is not None and len(self.summary) > 4000:
            self.summary = self.summary[0:4000]
        self.conv_storage.save_or_update(self)

    def load_from_storage(
        self, conv_storage: StorageInterface, message_storage: StorageInterface
    ) -> None:
        """Load the conversation from the storage.

        Warning: This will overwrite the current conversation.

        Args:
            conv_storage (StorageInterface): The storage interface
            message_storage (StorageInterface): The storage interface
        """
        # Load conversation first
        conversation: Optional[StorageConversation] = conv_storage.load(
            self._id, StorageConversation
        )
        if conversation is None:
            return
        message_ids = conversation._message_ids or []

        if self._load_message:
            # Load messages
            message_list = message_storage.load_list(
                [
                    MessageIdentifier.from_str_identifier(message_id)
                    for message_id in message_ids
                ],
                MessageStorageItem,
            )
            messages = [message.to_message() for message in message_list]
        else:
            messages = []
        real_messages = messages or conversation.messages
        conversation.messages = real_messages
        # This index is used to save the message to the storage(Has not been saved)
        # The new message append to the messages, so the index is len(messages)
        conversation._message_index = len(real_messages)
        conversation.chat_order = (
            max(m.round_index for m in real_messages) if real_messages else 0
        )
        self._append_additional_kwargs(conversation, real_messages)
        self._message_ids = message_ids
        self._has_stored_message_index = len(real_messages) - 1
        self.save_message_independent = conversation.save_message_independent
        self.from_conversation(conversation)

    def _append_additional_kwargs(
        self, conversation: StorageConversation, messages: List[BaseMessage]
    ) -> None:
        """Parse the additional kwargs and append to the conversation.

        Args:
            conversation (StorageConversation): The conversation
            messages (List[BaseMessage]): The messages
        """
        param_type = ""
        param_value = ""
        for message in messages[::-1]:
            if message.additional_kwargs:
                param_type = message.additional_kwargs.get("param_type", "")
                param_value = message.additional_kwargs.get("param_value", "")
                break
        if not conversation.param_type:
            conversation.param_type = param_type
        if not conversation.param_value:
            conversation.param_value = param_value

    def delete(self) -> None:
        """Delete all the messages and conversation."""
        # Delete messages first
        message_list = self._get_message_items()
        message_ids = [message.identifier for message in message_list]
        self.message_storage.delete_list(message_ids)
        # Delete conversation
        self.conv_storage.delete(self.identifier)
        # Overwrite the current conversation with empty conversation
        self.from_conversation(
            StorageConversation(
                self.conv_uid,
                save_message_independent=self.save_message_independent,
                conv_storage=self.conv_storage,
                message_storage=self.message_storage,
            )
        )

    def clear(self) -> None:
        """Clear all the messages and conversation."""
        from dbgpt_serve.agent.db import GptsConversationsDao, GptsMessagesDao

        # 清除Agent聊天记录
        GptsMessagesDao().delete_chat_message(conv_id=self.conv_uid)
        GptsConversationsDao().delete_chat_message(conv_id=self.conv_uid)

        # Clear messages first
        message_list = self._get_message_items()
        message_ids = [message.identifier for message in message_list]
        self.message_storage.delete_list(message_ids)
        # Clear conversation
        self.conv_storage.delete(self.identifier)
        # Overwrite the current conversation with empty conversation
        self.from_conversation(
            StorageConversation(
                self.conv_uid,
                save_message_independent=self.save_message_independent,
                conv_storage=self.conv_storage,
                message_storage=self.message_storage,
            )
        )


def _conversation_to_dict(once: OnceConversation) -> Dict:
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
        "summary": once.summary if once.summary else "",
    }


def _conversations_to_dict(conversations: List[OnceConversation]) -> List[dict]:
    return [_conversation_to_dict(m) for m in conversations]


def _conversation_from_dict(once: dict) -> OnceConversation:
    conversation = OnceConversation(
        once.get("chat_mode", ""), once.get("user_name"), once.get("sys_code")
    )
    conversation.cost = once.get("cost", 0)
    conversation.chat_mode = once.get("chat_mode", "chat_normal")
    conversation.tokens = once.get("tokens", 0)
    conversation.start_date = once.get("start_date", "")
    conversation.chat_order = int(once.get("chat_order", 0))
    conversation.param_type = once.get("param_type", "")
    conversation.param_value = once.get("param_value", "")
    conversation.model_name = once.get("model_name", "proxyllm")
    print(once.get("messages"))
    conversation.messages = _messages_from_dict(once.get("messages", []))
    return conversation


def _split_messages_by_round(messages: List[BaseMessage]) -> List[List[BaseMessage]]:
    """Split the messages by round index.

    Args:
        messages (List[BaseMessage]): The messages.

    Returns:
        List[List[BaseMessage]]: The messages split by round.
    """
    messages_by_round: List[List[BaseMessage]] = []
    last_round_index = 0
    for message in messages:
        if not message.round_index:
            # Round index must bigger than 0
            raise ValueError("Message round_index is not set")
        if message.round_index > last_round_index:
            last_round_index = message.round_index
            messages_by_round.append([])
        messages_by_round[-1].append(message)
    return messages_by_round


def _append_view_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Append the view message to the messages.

    Just for show in DB-GPT-Web.
    If already have view message, do nothing.

    Args:
        messages (List[BaseMessage]): The messages

    Returns:
        List[BaseMessage]: The messages with view message
    """
    messages_by_round = _split_messages_by_round(messages)
    for current_round in messages_by_round:
        ai_message = None
        view_message = None
        for message in current_round:
            if message.type == "ai":
                ai_message = message
            elif message.type == "view":
                view_message = message
        if view_message:
            # Already have view message, do nothing
            continue
        if ai_message:
            view_message = ViewMessage(
                content=ai_message.content,
                index=ai_message.index,
                round_index=ai_message.round_index,
                additional_kwargs=(
                    ai_message.additional_kwargs.copy()
                    if ai_message.additional_kwargs
                    else {}
                ),
            )
            current_round.append(view_message)
    return sum(messages_by_round, [])
