import uuid
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List, Optional

from dbgpt.core import (
    MessageStorageItem,
    ModelMessage,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.awel import BaseOperator, MapOperator, TransformStreamAbsOperator


class BaseConversationOperator(BaseOperator, ABC):
    """Base class for conversation operators."""

    SHARE_DATA_KEY_STORAGE_CONVERSATION = "share_data_key_storage_conversation"
    SHARE_DATA_KEY_MODEL_REQUEST = "share_data_key_model_request"

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs
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
        **kwargs
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

        chat_mode = input_value.context.extra.get("chat_mode")

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
        # The input message must be a single user message
        single_human_message: ModelMessage = input_value.get_single_user_message()
        storage_conv.start_new_round()
        storage_conv.add_user_message(single_human_message.content)

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
    def __init__(self, **kwargs):
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: ModelRequest) -> ModelRequest:
        """Map the input value to a ModelRequest.

        Args:
            input_value (ModelRequest): The input value.

        Returns:
            ModelRequest: The mapped ModelRequest.
        """
        input_value = input_value.copy()
        messages: List[ModelMessage] = await self.map_messages(input_value.messages)
        # Overwrite the input value
        input_value.messages = messages
        return input_value

    async def map_messages(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """Map the input messages to a list of ModelMessage.

        Args:
            messages (List[ModelMessage]): The input messages.

        Returns:
            List[ModelMessage]: The mapped ModelMessage.
        """
        return messages

    def _split_messages_by_round(
        self, messages: List[ModelMessage]
    ) -> List[List[ModelMessage]]:
        """Split the messages by round index.

        Args:
            messages (List[ModelMessage]): The input messages.

        Returns:
            List[List[ModelMessage]]: The splitted messages.
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

            import asyncio
            from dbgpt.core import ModelMessage
            from dbgpt.core.operator import BufferedConversationMapperOperator

            # No history
            messages = [ModelMessage(role="human", content="Hello", round_index=1)]
            operator = BufferedConversationMapperOperator(last_k_round=1)
            messages = asyncio.run(operator.map_messages(messages))
            assert messages == [ModelMessage(role="human", content="Hello", round_index=1)]

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
            messages = asyncio.run(operator.map_messages(messages))
            # Just keep the last one round, so the first round messages will be removed
            # Note: The round index 3 is not a complete round
            assert messages == [
                ModelMessage(role="system", content="Error 404", round_index=2),
                ModelMessage(role="human", content="What's the error?", round_index=2),
                ModelMessage(role="ai", content="Just a joke.", round_index=2),
                ModelMessage(role="human", content="Funny!", round_index=3),
            ]
    """

    def __init__(self, last_k_round: Optional[int] = 2, **kwargs):
        super().__init__(**kwargs)
        self._last_k_round = last_k_round

    async def map_messages(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """Map the input messages to a list of ModelMessage.

        Args:
            messages (List[ModelMessage]): The input messages.

        Returns:
            List[ModelMessage]: The mapped ModelMessage.
        """
        messages_by_round: List[List[ModelMessage]] = self._split_messages_by_round(
            messages
        )
        # Get the last k round messages
        index = self._last_k_round + 1
        messages_by_round = messages_by_round[-index:]
        messages: List[ModelMessage] = sum(messages_by_round, [])
        return messages
