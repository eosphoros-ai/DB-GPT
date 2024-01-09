import uuid
from abc import ABC
from typing import Any, Dict, List, Optional, Union

from dbgpt.core import (
    MessageStorageItem,
    ModelMessage,
    ModelMessageRoleType,
    ModelRequestContext,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.awel import BaseOperator, MapOperator
from dbgpt.core.interface.message import BaseMessage, _MultiRoundMessageMapper


class BaseConversationOperator(BaseOperator, ABC):
    """Base class for conversation operators."""

    SHARE_DATA_KEY_STORAGE_CONVERSATION = "share_data_key_storage_conversation"
    SHARE_DATA_KEY_MODEL_REQUEST = "share_data_key_model_request"
    SHARE_DATA_KEY_MODEL_REQUEST_CONTEXT = "share_data_key_model_request_context"

    _check_storage: bool = True

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        check_storage: bool = True,
        **kwargs,
    ):
        self._check_storage = check_storage
        super().__init__(**kwargs)
        self._storage = storage
        self._message_storage = message_storage

    @property
    def storage(self) -> Optional[StorageInterface[StorageConversation, Any]]:
        """Return the LLM client."""
        if not self._storage:
            if self._check_storage:
                raise ValueError("Storage is not set")
            return None
        return self._storage

    @property
    def message_storage(self) -> Optional[StorageInterface[MessageStorageItem, Any]]:
        """Return the LLM client."""
        if not self._message_storage:
            if self._check_storage:
                raise ValueError("Message storage is not set")
            return None
        return self._message_storage

    async def get_storage_conversation(self) -> Optional[StorageConversation]:
        """Get the storage conversation from share data.

        Returns:
            StorageConversation: The storage conversation.
        """
        storage_conv: StorageConversation = (
            await self.current_dag_context.get_from_share_data(
                self.SHARE_DATA_KEY_STORAGE_CONVERSATION
            )
        )
        if not storage_conv:
            if self._check_storage:
                raise ValueError("Storage conversation is not set")
            return None
        return storage_conv

    def check_messages(self, messages: List[ModelMessage]) -> None:
        """Check the messages.

        Args:
            messages (List[ModelMessage]): The messages.

        Raises:
            ValueError: If the messages is empty.
        """
        if not messages:
            raise ValueError("Input messages is empty")
        for message in messages:
            if message.role not in [
                ModelMessageRoleType.HUMAN,
                ModelMessageRoleType.SYSTEM,
            ]:
                raise ValueError(f"Message role {message.role} is not supported")


ChatHistoryLoadType = Union[ModelRequestContext, Dict[str, Any]]


class PreChatHistoryLoadOperator(
    BaseConversationOperator, MapOperator[ChatHistoryLoadType, List[BaseMessage]]
):
    """The operator to prepare the storage conversation.

    In DB-GPT, conversation record and the messages in the conversation are stored in the storage,
    and they can store in different storage(for high performance).

    This operator just load the conversation and messages from storage.
    """

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        include_system_message: bool = False,
        **kwargs,
    ):
        super().__init__(storage=storage, message_storage=message_storage)
        MapOperator.__init__(self, **kwargs)
        self._include_system_message = include_system_message

    async def map(self, input_value: ChatHistoryLoadType) -> List[BaseMessage]:
        """Map the input value to a ModelRequest.

        Args:
            input_value (ChatHistoryLoadType): The input value.

        Returns:
            List[BaseMessage]: The messages stored in the storage.
        """
        if not input_value:
            raise ValueError("Model request context can't be None")
        if isinstance(input_value, dict):
            input_value = ModelRequestContext(**input_value)
        if not input_value.conv_uid:
            input_value.conv_uid = str(uuid.uuid4())
        if not input_value.extra:
            input_value.extra = {}

        chat_mode = input_value.chat_mode

        # Create a new storage conversation, this will load the conversation from storage, so we must do this async
        storage_conv: StorageConversation = await self.blocking_func_to_async(
            StorageConversation,
            conv_uid=input_value.conv_uid,
            chat_mode=chat_mode,
            user_name=input_value.user_name,
            sys_code=input_value.sys_code,
            conv_storage=self.storage,
            message_storage=self.message_storage,
        )

        # Save the storage conversation to share data, for the child operators
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_STORAGE_CONVERSATION, storage_conv
        )
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_MODEL_REQUEST_CONTEXT, input_value
        )
        # Get history messages from storage
        history_messages: List[BaseMessage] = storage_conv.get_history_message(
            include_system_message=self._include_system_message
        )
        return history_messages


class ConversationMapperOperator(
    BaseConversationOperator, MapOperator[List[BaseMessage], List[BaseMessage]]
):
    def __init__(self, message_mapper: _MultiRoundMessageMapper = None, **kwargs):
        MapOperator.__init__(self, **kwargs)
        self._message_mapper = message_mapper

    async def map(self, input_value: List[BaseMessage]) -> List[BaseMessage]:
        return self.map_messages(input_value)

    def map_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        messages_by_round: List[List[BaseMessage]] = self._split_messages_by_round(
            messages
        )
        message_mapper = self._message_mapper or self.map_multi_round_messages
        return message_mapper(messages_by_round)

    def map_multi_round_messages(
        self, messages_by_round: List[List[BaseMessage]]
    ) -> List[BaseMessage]:
        """Map multi round messages to a list of BaseMessage.

        By default, just merge all multi round messages to a list of BaseMessage according origin order.
        And you can overwrite this method to implement your own logic.

        Examples:

            Merge multi round messages to a list of BaseMessage according origin order.

            >>> from dbgpt.core.interface.message import (
            ...     AIMessage,
            ...     HumanMessage,
            ...     SystemMessage,
            ... )
            >>> messages_by_round = [
            ...     [
            ...         HumanMessage(content="Hi", round_index=1),
            ...         AIMessage(content="Hello!", round_index=1),
            ...     ],
            ...     [
            ...         HumanMessage(content="What's the error?", round_index=2),
            ...         AIMessage(content="Just a joke.", round_index=2),
            ...     ],
            ... ]
            >>> operator = ConversationMapperOperator()
            >>> messages = operator.map_multi_round_messages(messages_by_round)
            >>> assert messages == [
            ...     HumanMessage(content="Hi", round_index=1),
            ...     AIMessage(content="Hello!", round_index=1),
            ...     HumanMessage(content="What's the error?", round_index=2),
            ...     AIMessage(content="Just a joke.", round_index=2),
            ... ]

            Map multi round messages to a list of BaseMessage just keep the last one round.

            >>> class MyMapper(ConversationMapperOperator):
            ...     def __init__(self, **kwargs):
            ...         super().__init__(**kwargs)
            ...
            ...     def map_multi_round_messages(
            ...         self, messages_by_round: List[List[BaseMessage]]
            ...     ) -> List[BaseMessage]:
            ...         return messages_by_round[-1]
            ...
            >>> operator = MyMapper()
            >>> messages = operator.map_multi_round_messages(messages_by_round)
            >>> assert messages == [
            ...     HumanMessage(content="What's the error?", round_index=2),
            ...     AIMessage(content="Just a joke.", round_index=2),
            ... ]

        Args:
        """
        # Just merge and return
        # e.g. assert sum([[1, 2], [3, 4], [5, 6]], []) == [1, 2, 3, 4, 5, 6]
        return sum(messages_by_round, [])

    def _split_messages_by_round(
        self, messages: List[BaseMessage]
    ) -> List[List[BaseMessage]]:
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


class BufferedConversationMapperOperator(ConversationMapperOperator):
    """The buffered conversation mapper operator.

    This Operator must be used after the PreChatHistoryLoadOperator,
        and it will map the messages in the storage conversation.

    Examples:

        Transform no history messages

        .. code-block:: python

            from dbgpt.core import ModelMessage
            from dbgpt.core.operator import BufferedConversationMapperOperator

            # No history
            messages = [ModelMessage(role="human", content="Hello", round_index=1)]
            operator = BufferedConversationMapperOperator(last_k_round=1)
            assert operator.map_messages(messages) == [
                ModelMessage(role="human", content="Hello", round_index=1)
            ]

        Transform with history messages

        .. code-block:: python

            # With history
            messages = [
                ModelMessage(role="human", content="Hi", round_index=1),
                ModelMessage(role="ai", content="Hello!", round_index=1),
                ModelMessage(role="system", content="Error 404", round_index=2),
                ModelMessage(role="human", content="What's the error?", round_index=2),
                ModelMessage(role="ai", content="Just a joke.", round_index=2),
                ModelMessage(role="human", content="Funny!", round_index=3),
            ]
            operator = BufferedConversationMapperOperator(last_k_round=1)
            # Just keep the last one round, so the first round messages will be removed
            # Note: The round index 3 is not a complete round
            assert operator.map_messages(messages) == [
                ModelMessage(role="system", content="Error 404", round_index=2),
                ModelMessage(role="human", content="What's the error?", round_index=2),
                ModelMessage(role="ai", content="Just a joke.", round_index=2),
                ModelMessage(role="human", content="Funny!", round_index=3),
            ]
    """

    def __init__(
        self,
        last_k_round: Optional[int] = 2,
        message_mapper: _MultiRoundMessageMapper = None,
        **kwargs,
    ):
        self._last_k_round = last_k_round
        if message_mapper:

            def new_message_mapper(
                messages_by_round: List[List[BaseMessage]],
            ) -> List[BaseMessage]:
                # Apply keep k round messages first, then apply the custom message mapper
                messages_by_round = self._keep_last_round_messages(messages_by_round)
                return message_mapper(messages_by_round)

        else:

            def new_message_mapper(
                messages_by_round: List[List[BaseMessage]],
            ) -> List[BaseMessage]:
                messages_by_round = self._keep_last_round_messages(messages_by_round)
                return sum(messages_by_round, [])

        super().__init__(new_message_mapper, **kwargs)

    def _keep_last_round_messages(
        self, messages_by_round: List[List[BaseMessage]]
    ) -> List[List[BaseMessage]]:
        """Keep the last k round messages.

        Args:
            messages_by_round (List[List[BaseMessage]]): The messages by round.

        Returns:
            List[List[BaseMessage]]: The latest round messages.
        """
        index = self._last_k_round + 1
        return messages_by_round[-index:]
