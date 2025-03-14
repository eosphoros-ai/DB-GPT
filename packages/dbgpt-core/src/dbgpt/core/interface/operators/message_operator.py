"""The message operator."""

import logging
import uuid
from abc import ABC
from typing import Any, Callable, Dict, List, Optional, Union, cast

from dbgpt.core import (
    InMemoryStorage,
    LLMClient,
    MessageStorageItem,
    ModelMessage,
    ModelMessageRoleType,
    ModelRequest,
    ModelRequestContext,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.awel import BaseOperator, MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.core.interface.message import (
    BaseMessage,
    _messages_to_str,
    _MultiRoundMessageMapper,
    _split_messages_by_round,
)
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


class BaseConversationOperator(BaseOperator, ABC):
    """Base class for conversation operators."""

    SHARE_DATA_KEY_CONV_MODEL_NAME = "conv_share_data_key_model_name"
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
        """Create a new BaseConversationOperator."""
        self._check_storage = check_storage
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


ChatHistoryLoadType = Union[ModelRequest, ModelRequestContext, Dict[str, Any]]


class PreChatHistoryLoadOperator(
    BaseConversationOperator, MapOperator[ChatHistoryLoadType, List[BaseMessage]]
):
    """The operator to prepare the storage conversation.

    In DB-GPT, conversation record and the messages in the conversation are stored in
    the storage,
    and they can store in different storage(for high performance).

    This operator just load the conversation and messages from storage.
    """

    metadata = ViewMetadata(
        label=_("Chat History Load Operator"),
        name="chat_history_load_operator",
        category=OperatorCategory.CONVERSION,
        description=_("The operator to load chat history from storage."),
        parameters=[
            Parameter.build_from(
                label=_("Conversation Storage"),
                name="storage",
                type=StorageInterface,
                optional=True,
                default=None,
                description=_(
                    "The conversation storage, store the conversation items("
                    "Not include message items). If None, we will use InMemoryStorage."
                ),
            ),
            Parameter.build_from(
                label=_("Message Storage"),
                name="message_storage",
                type=StorageInterface,
                optional=True,
                default=None,
                description=_(
                    "The message storage, store the messages of one "
                    "conversation. If None, we will use InMemoryStorage."
                ),
            ),
        ],
        inputs=[
            IOField.build_from(
                label=_("Model Request"),
                name="input_value",
                type=ModelRequest,
                description=_("The model request."),
            )
        ],
        outputs=[
            IOField.build_from(
                label=_("Stored Messages"),
                name="output_value",
                type=BaseMessage,
                description=_("The messages stored in the storage."),
                is_list=True,
            )
        ],
    )

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        include_system_message: bool = False,
        use_in_memory_storage_if_not_set: bool = True,
        **kwargs,
    ):
        """Create a new PreChatHistoryLoadOperator."""
        if not storage and use_in_memory_storage_if_not_set:
            logger.info(
                "Storage is not set, use the InMemoryStorage as the conversation "
                "storage."
            )
            storage = InMemoryStorage()
        if not message_storage and use_in_memory_storage_if_not_set:
            logger.info(
                "Message storage is not set, use the InMemoryStorage as the message "
            )
            message_storage = InMemoryStorage()
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
        elif isinstance(input_value, ModelRequest):
            if not input_value.context:
                raise ValueError("Model request context can't be None")
            input_value = input_value.context
        input_value = cast(ModelRequestContext, input_value)
        if not input_value.conv_uid:
            input_value.conv_uid = str(uuid.uuid4())
        if not input_value.extra:
            input_value.extra = {}

        chat_mode = input_value.chat_mode

        # Create a new storage conversation, this will load the conversation from
        # storage, so we must do this async
        storage_conv: StorageConversation = await self.blocking_func_to_async(
            StorageConversation,
            conv_uid=input_value.conv_uid,
            chat_mode=chat_mode,
            user_name=input_value.user_name,
            sys_code=input_value.sys_code,
            conv_storage=self.storage,
            message_storage=self.message_storage,
            param_type="",
            param_value=input_value.chat_param,
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
    """The base conversation mapper operator."""

    def __init__(
        self, message_mapper: Optional[_MultiRoundMessageMapper] = None, **kwargs
    ):
        """Create a new ConversationMapperOperator."""
        MapOperator.__init__(self, **kwargs)
        self._message_mapper = message_mapper

    async def map(self, input_value: List[BaseMessage]) -> List[BaseMessage]:
        """Map the input value to a ModelRequest."""
        return await self.map_messages(input_value)

    async def map_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Map multi round messages to a list of BaseMessage."""
        messages_by_round: List[List[BaseMessage]] = _split_messages_by_round(messages)
        message_mapper = self._message_mapper or self.map_multi_round_messages
        return message_mapper(messages_by_round)

    def map_multi_round_messages(
        self, messages_by_round: List[List[BaseMessage]]
    ) -> List[BaseMessage]:
        """Map multi round messages to a list of BaseMessage.

        By default, just merge all multi round messages to a list of BaseMessage
        according origin order.
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

            Map multi round messages to a list of BaseMessage just keep the last one
            round.

            >>> class MyMapper(ConversationMapperOperator):
            ...     def __init__(self, **kwargs):
            ...         super().__init__(**kwargs)
            ...
            ...     def map_multi_round_messages(
            ...         self, messages_by_round: List[List[BaseMessage]]
            ...     ) -> List[BaseMessage]:
            ...         return messages_by_round[-1]
            >>> operator = MyMapper()
            >>> messages = operator.map_multi_round_messages(messages_by_round)
            >>> assert messages == [
            ...     HumanMessage(content="What's the error?", round_index=2),
            ...     AIMessage(content="Just a joke.", round_index=2),
            ... ]

        Args:
            messages_by_round (List[List[BaseMessage]]):
                The messages grouped by round.
        """
        # Just merge and return
        return _merge_multi_round_messages(messages_by_round)


class BufferedConversationMapperOperator(ConversationMapperOperator):
    """Buffered conversation mapper operator.

    The buffered conversation mapper operator which can be configured to keep
    a certain number of starting and/or ending rounds of a conversation.

    Args:
        keep_start_rounds (Optional[int]): Number of initial rounds to keep.
        keep_end_rounds (Optional[int]): Number of final rounds to keep.

    Examples:
        .. code-block:: python

            # Keeping the first 2 and the last 1 rounds of a conversation
            import asyncio
            from dbgpt.core.interface.message import AIMessage, HumanMessage
            from dbgpt.core.operators import BufferedConversationMapperOperator

            operator = BufferedConversationMapperOperator(
                keep_start_rounds=2, keep_end_rounds=1
            )
            messages = [
                # Assume each HumanMessage and AIMessage belongs to separate rounds
                HumanMessage(content="Hi", round_index=1),
                AIMessage(content="Hello!", round_index=1),
                HumanMessage(content="How are you?", round_index=2),
                AIMessage(content="I'm good, thanks!", round_index=2),
                HumanMessage(content="What's new today?", round_index=3),
                AIMessage(content="Lots of things!", round_index=3),
            ]
            # This will keep rounds 1, 2, and 3
            assert asyncio.run(operator.map_messages(messages)) == [
                HumanMessage(content="Hi", round_index=1),
                AIMessage(content="Hello!", round_index=1),
                HumanMessage(content="How are you?", round_index=2),
                AIMessage(content="I'm good, thanks!", round_index=2),
                HumanMessage(content="What's new today?", round_index=3),
                AIMessage(content="Lots of things!", round_index=3),
            ]
    """

    def __init__(
        self,
        keep_start_rounds: Optional[int] = None,
        keep_end_rounds: Optional[int] = None,
        message_mapper: Optional[_MultiRoundMessageMapper] = None,
        **kwargs,
    ):
        """Create a new BufferedConversationMapperOperator."""
        # Validate the input parameters
        if keep_start_rounds is None:
            keep_start_rounds = 0
        if keep_end_rounds is None:
            keep_end_rounds = 0
        if keep_start_rounds < 0:
            raise ValueError("keep_start_rounds must be non-negative")
        if keep_end_rounds < 0:
            raise ValueError("keep_end_rounds must be non-negative")

        self._keep_start_rounds = keep_start_rounds
        self._keep_end_rounds = keep_end_rounds
        if message_mapper:

            def new_message_mapper(
                messages_by_round: List[List[BaseMessage]],
            ) -> List[BaseMessage]:
                messages_by_round = self._filter_round_messages(messages_by_round)
                return message_mapper(messages_by_round)

        else:

            def new_message_mapper(
                messages_by_round: List[List[BaseMessage]],
            ) -> List[BaseMessage]:
                messages_by_round = self._filter_round_messages(messages_by_round)
                return _merge_multi_round_messages(messages_by_round)

        super().__init__(new_message_mapper, **kwargs)

    def _filter_round_messages(
        self, messages_by_round: List[List[BaseMessage]]
    ) -> List[List[BaseMessage]]:
        """Return a filtered list of messages.

        Filters the messages to keep only the specified starting and/or ending rounds.

        Examples:
            >>> from dbgpt.core import AIMessage, HumanMessage
            >>> from dbgpt.core.operators import BufferedConversationMapperOperator
            >>> messages = [
            ...     [
            ...         HumanMessage(content="Hi", round_index=1),
            ...         AIMessage(content="Hello!", round_index=1),
            ...     ],
            ...     [
            ...         HumanMessage(content="How are you?", round_index=2),
            ...         AIMessage(content="I'm good, thanks!", round_index=2),
            ...     ],
            ...     [
            ...         HumanMessage(content="What's new today?", round_index=3),
            ...         AIMessage(content="Lots of things!", round_index=3),
            ...     ],
            ... ]

            >>> # Test keeping only the first 2 rounds
            >>> operator = BufferedConversationMapperOperator(keep_start_rounds=2)
            >>> assert operator._filter_round_messages(messages) == [
            ...     [
            ...         HumanMessage(content="Hi", round_index=1),
            ...         AIMessage(content="Hello!", round_index=1),
            ...     ],
            ...     [
            ...         HumanMessage(content="How are you?", round_index=2),
            ...         AIMessage(content="I'm good, thanks!", round_index=2),
            ...     ],
            ... ]

            >>> # Test keeping only the last 2 rounds
            >>> operator = BufferedConversationMapperOperator(keep_end_rounds=2)
            >>> assert operator._filter_round_messages(messages) == [
            ...     [
            ...         HumanMessage(content="How are you?", round_index=2),
            ...         AIMessage(content="I'm good, thanks!", round_index=2),
            ...     ],
            ...     [
            ...         HumanMessage(content="What's new today?", round_index=3),
            ...         AIMessage(content="Lots of things!", round_index=3),
            ...     ],
            ... ]

            >>> # Test keeping the first 2 and last 1 rounds
            >>> operator = BufferedConversationMapperOperator(
            ...     keep_start_rounds=2, keep_end_rounds=1
            ... )
            >>> assert operator._filter_round_messages(messages) == [
            ...     [
            ...         HumanMessage(content="Hi", round_index=1),
            ...         AIMessage(content="Hello!", round_index=1),
            ...     ],
            ...     [
            ...         HumanMessage(content="How are you?", round_index=2),
            ...         AIMessage(content="I'm good, thanks!", round_index=2),
            ...     ],
            ...     [
            ...         HumanMessage(content="What's new today?", round_index=3),
            ...         AIMessage(content="Lots of things!", round_index=3),
            ...     ],
            ... ]

            >>> # Test without specifying start or end rounds (keep 0 rounds)
            >>> operator = BufferedConversationMapperOperator()
            >>> assert operator._filter_round_messages(messages) == []

            >>> # Test end rounds is zero
            >>> operator = BufferedConversationMapperOperator(
            ...     keep_start_rounds=1, keep_end_rounds=0
            ... )
            >>> assert operator._filter_round_messages(messages) == [
            ...     [
            ...         HumanMessage(content="Hi", round_index=1),
            ...         AIMessage(content="Hello!", round_index=1),
            ...     ]
            ... ]


        Args:
            messages_by_round (List[List[BaseMessage]]):
                The messages grouped by round.

        Returns:
            List[List[BaseMessage]]: Filtered list of messages.

        """
        total_rounds = len(messages_by_round)
        if self._keep_start_rounds > 0 and self._keep_end_rounds > 0:
            if self._keep_start_rounds + self._keep_end_rounds > total_rounds:
                # Avoid overlapping when the sum of start and end rounds exceeds total
                # rounds
                return messages_by_round
            return (
                messages_by_round[: self._keep_start_rounds]
                + messages_by_round[-self._keep_end_rounds :]
            )
        elif self._keep_start_rounds:
            return messages_by_round[: self._keep_start_rounds]
        elif self._keep_end_rounds:
            return messages_by_round[-self._keep_end_rounds :]
        else:
            return []


EvictionPolicyType = Callable[[List[List[BaseMessage]]], List[List[BaseMessage]]]


class TokenBufferedConversationMapperOperator(ConversationMapperOperator):
    """The token buffered conversation mapper operator.

    If the token count of the messages is greater than the max token limit, we will
    evict the messages by round.

    Args:
        model (str): The model name.
        llm_client (LLMClient): The LLM client.
        max_token_limit (int): The max token limit.
        eviction_policy (EvictionPolicyType): The eviction policy.
        message_mapper (_MultiRoundMessageMapper): The message mapper, it applies after
            all messages are handled.
    """

    def __init__(
        self,
        model: str,
        llm_client: LLMClient,
        max_token_limit: int = 2000,
        eviction_policy: Optional[EvictionPolicyType] = None,
        message_mapper: Optional[_MultiRoundMessageMapper] = None,
        **kwargs,
    ):
        """Create a new TokenBufferedConversationMapperOperator."""
        if max_token_limit < 0:
            raise ValueError("Max token limit can't be negative")
        self._model = model
        self._llm_client = llm_client
        self._max_token_limit = max_token_limit
        self._eviction_policy = eviction_policy
        self._message_mapper = message_mapper
        super().__init__(**kwargs)

    async def map_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Map multi round messages to a list of BaseMessage."""
        eviction_policy = self._eviction_policy or self.eviction_policy
        messages_by_round: List[List[BaseMessage]] = _split_messages_by_round(messages)
        messages_str = _messages_to_str(_merge_multi_round_messages(messages_by_round))
        model_name = self._model
        if not model_name:
            model_name = await self.current_dag_context.get_from_share_data(
                self.SHARE_DATA_KEY_CONV_MODEL_NAME
            )
        # Fist time, we count the token of the messages
        current_tokens = await self._llm_client.count_token(model_name, messages_str)

        while current_tokens > self._max_token_limit:
            # Evict the messages by round after all tokens are not greater than the max
            # token limit
            # TODO: We should find a high performance way to do this
            messages_by_round = eviction_policy(messages_by_round)
            messages_str = _messages_to_str(
                _merge_multi_round_messages(messages_by_round)
            )
            current_tokens = await self._llm_client.count_token(
                model_name, messages_str
            )
        message_mapper = self._message_mapper or self.map_multi_round_messages
        return message_mapper(messages_by_round)

    def eviction_policy(
        self, messages_by_round: List[List[BaseMessage]]
    ) -> List[List[BaseMessage]]:
        """Evict the messages by round, default is FIFO.

        Args:
            messages_by_round (List[List[BaseMessage]]): The messages by round.

        Returns:
            List[List[BaseMessage]]: The evicted messages by round.
        """
        messages_by_round.pop(0)
        return messages_by_round


def _merge_multi_round_messages(messages: List[List[BaseMessage]]) -> List[BaseMessage]:
    # e.g. assert sum([[1, 2], [3, 4], [5, 6]], []) == [1, 2, 3, 4, 5, 6]
    return sum(messages, [])
