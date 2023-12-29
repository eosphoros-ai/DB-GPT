import uuid
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List, Optional

from dbgpt.core import (
    MessageStorageItem,
    ModelMessage,
    ModelMessageRoleType,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.awel import BaseOperator, MapOperator, TransformStreamAbsOperator
from dbgpt.core.interface.message import _MultiRoundMessageMapper


class BaseConversationOperator(BaseOperator, ABC):
    """Base class for conversation operators."""

    SHARE_DATA_KEY_STORAGE_CONVERSATION = "share_data_key_storage_conversation"
    SHARE_DATA_KEY_MODEL_REQUEST = "share_data_key_model_request"

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._storage = storage
        self._message_storage = message_storage

    @property
    def storage(self) -> StorageInterface[StorageConversation, Any]:
        """Return the LLM client."""
        if not self._storage:
            raise ValueError("Storage is not set")
        return self._storage

    @property
    def message_storage(self) -> StorageInterface[MessageStorageItem, Any]:
        """Return the LLM client."""
        if not self._message_storage:
            raise ValueError("Message storage is not set")
        return self._message_storage

    async def get_storage_conversation(self) -> StorageConversation:
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
            raise ValueError("Storage conversation is not set")
        return storage_conv

    async def get_model_request(self) -> ModelRequest:
        """Get the model request from share data.

        Returns:
            ModelRequest: The model request.
        """
        model_request: ModelRequest = (
            await self.current_dag_context.get_from_share_data(
                self.SHARE_DATA_KEY_MODEL_REQUEST
            )
        )
        if not model_request:
            raise ValueError("Model request is not set")
        return model_request


class PreConversationOperator(
    BaseConversationOperator, MapOperator[ModelRequest, ModelRequest]
):
    """The operator to prepare the storage conversation.

    In DB-GPT, conversation record and the messages in the conversation are stored in the storage,
    and they can store in different storage(for high performance).
    """

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs,
    ):
        super().__init__(storage=storage, message_storage=message_storage)
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: ModelRequest) -> ModelRequest:
        """Map the input value to a ModelRequest.

        Args:
            input_value (ModelRequest): The input value.

        Returns:
            ModelRequest: The mapped ModelRequest.
        """
        if input_value.context is None:
            input_value.context = ModelRequestContext()
        if not input_value.context.conv_uid:
            input_value.context.conv_uid = str(uuid.uuid4())
        if not input_value.context.extra:
            input_value.context.extra = {}

        chat_mode = input_value.context.chat_mode

        # Create a new storage conversation, this will load the conversation from storage, so we must do this async
        storage_conv: StorageConversation = await self.blocking_func_to_async(
            StorageConversation,
            conv_uid=input_value.context.conv_uid,
            chat_mode=chat_mode,
            user_name=input_value.context.user_name,
            sys_code=input_value.context.sys_code,
            conv_storage=self.storage,
            message_storage=self.message_storage,
        )
        input_messages = input_value.get_messages()
        await self.save_to_storage(storage_conv, input_messages)
        # Get all messages from current storage conversation, and overwrite the input value
        messages: List[ModelMessage] = storage_conv.get_model_messages()
        input_value.messages = messages

        # Save the storage conversation to share data, for the child operators
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_STORAGE_CONVERSATION, storage_conv
        )
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_MODEL_REQUEST, input_value
        )
        return input_value

    async def save_to_storage(
        self, storage_conv: StorageConversation, input_messages: List[ModelMessage]
    ) -> None:
        """Save the messages to storage.

        Args:
            storage_conv (StorageConversation): The storage conversation.
            input_messages (List[ModelMessage]): The input messages.
        """
        # check first
        self.check_messages(input_messages)
        storage_conv.start_new_round()
        for message in input_messages:
            if message.role == ModelMessageRoleType.HUMAN:
                storage_conv.add_user_message(message.content)
            else:
                storage_conv.add_system_message(message.content)

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

    async def after_dag_end(self):
        """The callback after DAG end"""
        # Save the storage conversation to storage after the whole DAG finished
        storage_conv: StorageConversation = await self.get_storage_conversation()
        # TODO dont save if the conversation has some internal error
        storage_conv.end_current_round()


class PostConversationOperator(
    BaseConversationOperator, MapOperator[ModelOutput, ModelOutput]
):
    def __init__(self, **kwargs):
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: ModelOutput) -> ModelOutput:
        """Map the input value to a ModelOutput.

        Args:
            input_value (ModelOutput): The input value.

        Returns:
            ModelOutput: The mapped ModelOutput.
        """
        # Get the storage conversation from share data
        storage_conv: StorageConversation = await self.get_storage_conversation()
        storage_conv.add_ai_message(input_value.text)
        return input_value


class PostStreamingConversationOperator(
    BaseConversationOperator, TransformStreamAbsOperator[ModelOutput, ModelOutput]
):
    def __init__(self, **kwargs):
        TransformStreamAbsOperator.__init__(self, **kwargs)

    async def transform_stream(
        self, input_value: AsyncIterator[ModelOutput]
    ) -> ModelOutput:
        """Transform the input value to a ModelOutput.

        Args:
            input_value (ModelOutput): The input value.

        Returns:
            ModelOutput: The transformed ModelOutput.
        """
        full_text = ""
        async for model_output in input_value:
            # Now model_output.text if full text, if it is a delta text, we should merge all delta text to a full text
            full_text = model_output.text
            yield model_output
        # Get the storage conversation from share data
        storage_conv: StorageConversation = await self.get_storage_conversation()
        storage_conv.add_ai_message(full_text)


class ConversationMapperOperator(
    BaseConversationOperator, MapOperator[ModelRequest, ModelRequest]
):
    def __init__(self, message_mapper: _MultiRoundMessageMapper = None, **kwargs):
        MapOperator.__init__(self, **kwargs)
        self._message_mapper = message_mapper

    async def map(self, input_value: ModelRequest) -> ModelRequest:
        """Map the input value to a ModelRequest.

        Args:
            input_value (ModelRequest): The input value.

        Returns:
            ModelRequest: The mapped ModelRequest.
        """
        input_value = input_value.copy()
        messages: List[ModelMessage] = self.map_messages(input_value.messages)
        # Overwrite the input value
        input_value.messages = messages
        return input_value

    def map_messages(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """Map the input messages to a list of ModelMessage.

        Args:
            messages (List[ModelMessage]): The input messages.

        Returns:
            List[ModelMessage]: The mapped ModelMessage.
        """
        messages_by_round: List[List[ModelMessage]] = self._split_messages_by_round(
            messages
        )
        message_mapper = self._message_mapper or self.map_multi_round_messages
        return message_mapper(messages_by_round)

    def map_multi_round_messages(
        self, messages_by_round: List[List[ModelMessage]]
    ) -> List[ModelMessage]:
        """Map multi round messages to a list of ModelMessage

        By default, just merge all multi round messages to a list of ModelMessage according origin order.
        And you can overwrite this method to implement your own logic.

        Examples:

            Merge multi round messages to a list of ModelMessage according origin order.

            .. code-block:: python

                import asyncio
                from dbgpt.core.operator import ConversationMapperOperator

                messages_by_round = [
                    [
                        ModelMessage(role="human", content="Hi", round_index=1),
                        ModelMessage(role="ai", content="Hello!", round_index=1),
                    ],
                    [
                        ModelMessage(role="system", content="Error 404", round_index=2),
                        ModelMessage(
                            role="human", content="What's the error?", round_index=2
                        ),
                        ModelMessage(role="ai", content="Just a joke.", round_index=2),
                    ],
                    [
                        ModelMessage(role="human", content="Funny!", round_index=3),
                    ],
                ]
                operator = ConversationMapperOperator()
                messages = operator.map_multi_round_messages(messages_by_round)
                assert messages == [
                    ModelMessage(role="human", content="Hi", round_index=1),
                    ModelMessage(role="ai", content="Hello!", round_index=1),
                    ModelMessage(role="system", content="Error 404", round_index=2),
                    ModelMessage(
                        role="human", content="What's the error?", round_index=2
                    ),
                    ModelMessage(role="ai", content="Just a joke.", round_index=2),
                    ModelMessage(role="human", content="Funny!", round_index=3),
                ]

            Map multi round messages to a list of ModelMessage just keep the last one round.

            .. code-block:: python

                class MyMapper(ConversationMapperOperator):
                    def __init__(self, **kwargs):
                        super().__init__(**kwargs)

                    def map_multi_round_messages(
                        self, messages_by_round: List[List[ModelMessage]]
                    ) -> List[ModelMessage]:
                        return messages_by_round[-1]


                operator = MyMapper()
                messages = operator.map_multi_round_messages(messages_by_round)
                assert messages == [
                    ModelMessage(role="human", content="Funny!", round_index=3),
                ]

        Args:
        """
        # Just merge and return
        # e.g. assert sum([[1, 2], [3, 4], [5, 6]], []) == [1, 2, 3, 4, 5, 6]
        return sum(messages_by_round, [])

    def _split_messages_by_round(
        self, messages: List[ModelMessage]
    ) -> List[List[ModelMessage]]:
        """Split the messages by round index.

        Args:
            messages (List[ModelMessage]): The input messages.

        Returns:
            List[List[ModelMessage]]: The split messages.
        """
        messages_by_round: List[List[ModelMessage]] = []
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

    This Operator must be used after the PreConversationOperator,
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
                messages_by_round: List[List[ModelMessage]],
            ) -> List[ModelMessage]:
                # Apply keep k round messages first, then apply the custom message mapper
                messages_by_round = self._keep_last_round_messages(messages_by_round)
                return message_mapper(messages_by_round)

        else:

            def new_message_mapper(
                messages_by_round: List[List[ModelMessage]],
            ) -> List[ModelMessage]:
                messages_by_round = self._keep_last_round_messages(messages_by_round)
                return sum(messages_by_round, [])

        super().__init__(new_message_mapper, **kwargs)

    def _keep_last_round_messages(
        self, messages_by_round: List[List[ModelMessage]]
    ) -> List[List[ModelMessage]]:
        """Keep the last k round messages.

        Args:
            messages_by_round (List[List[ModelMessage]]): The messages by round.

        Returns:
            List[List[ModelMessage]]: The latest round messages.
        """
        index = self._last_k_round + 1
        return messages_by_round[-index:]
