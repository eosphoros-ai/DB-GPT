from abc import ABC
from typing import Any, Dict, List, Optional, Union

from dbgpt.core import (
    BasePromptTemplate,
    ChatPromptTemplate,
    ModelMessage,
    ModelMessageRoleType,
    ModelOutput,
    StorageConversation,
)
from dbgpt.core.awel import JoinOperator, MapOperator
from dbgpt.core.interface.message import BaseMessage
from dbgpt.core.interface.operator.llm_operator import BaseLLM
from dbgpt.core.interface.operator.message_operator import BaseConversationOperator
from dbgpt.core.interface.prompt import HumanPromptTemplate, MessageType
from dbgpt.util.function_utils import rearrange_args_by_type


class BasePromptBuilderOperator(BaseConversationOperator, ABC):
    """The base prompt builder operator."""

    def __init__(self, check_storage: bool, **kwargs):
        super().__init__(check_storage=check_storage, **kwargs)

    async def format_prompt(
        self, prompt: ChatPromptTemplate, prompt_dict: Dict[str, Any]
    ) -> List[ModelMessage]:
        """Format the prompt.

        Args:
            prompt (ChatPromptTemplate): The prompt.
            prompt_dict (Dict[str, Any]): The prompt dict.

        Returns:
            List[ModelMessage]: The formatted prompt.
        """
        kwargs = {}
        kwargs.update(prompt_dict)
        pass_kwargs = {k: v for k, v in kwargs.items() if k in prompt.input_variables}
        messages = prompt.format_messages(**pass_kwargs)
        messages = ModelMessage.from_base_messages(messages)
        # Start new round conversation, and save user message to storage
        await self.start_new_round_conv(messages)
        return messages

    async def start_new_round_conv(self, messages: List[ModelMessage]) -> None:
        """Start a new round conversation.

        Args:
            messages (List[ModelMessage]): The messages.
        """

        lass_user_message = None
        for message in messages[::-1]:
            if message.role == ModelMessageRoleType.HUMAN:
                lass_user_message = message.content
                break
        if not lass_user_message:
            raise ValueError("No user message")
        storage_conv: StorageConversation = await self.get_storage_conversation()
        if not storage_conv:
            return
        # Start new round
        storage_conv.start_new_round()
        storage_conv.add_user_message(lass_user_message)

    async def after_dag_end(self):
        """The callback after DAG end"""
        # TODO remove this to start_new_round()
        # Save the storage conversation to storage after the whole DAG finished
        storage_conv: StorageConversation = await self.get_storage_conversation()
        if not storage_conv:
            return
        model_output: ModelOutput = await self.current_dag_context.get_from_share_data(
            BaseLLM.SHARE_DATA_KEY_MODEL_OUTPUT
        )
        if model_output:
            # Save model output message to storage
            storage_conv.add_ai_message(model_output.text)
            # End current conversation round and flush to storage
            storage_conv.end_current_round()


PromptTemplateType = Union[ChatPromptTemplate, BasePromptTemplate, MessageType, str]


class PromptBuilderOperator(
    BasePromptBuilderOperator, MapOperator[Dict[str, Any], List[ModelMessage]]
):
    """The operator to build the prompt with static prompt.

    Examples:

        .. code-block:: python

            import asyncio
            from dbgpt.core.awel import DAG
            from dbgpt.core import (
                ModelMessage,
                HumanMessage,
                SystemMessage,
                HumanPromptTemplate,
                SystemPromptTemplate,
                ChatPromptTemplate,
            )
            from dbgpt.core.operator import PromptBuilderOperator

            with DAG("prompt_test") as dag:
                str_prompt = PromptBuilderOperator(
                    "Please write a {dialect} SQL count the length of a field"
                )
                tp_prompt = PromptBuilderOperator(
                    HumanPromptTemplate.from_template(
                        "Please write a {dialect} SQL count the length of a field"
                    )
                )
                chat_prompt = PromptBuilderOperator(
                    ChatPromptTemplate(
                        messages=[
                            HumanPromptTemplate.from_template(
                                "Please write a {dialect} SQL count the length of a field"
                            )
                        ]
                    )
                )
                with_sys_prompt = PromptBuilderOperator(
                    ChatPromptTemplate(
                        messages=[
                            SystemPromptTemplate.from_template(
                                "You are a {dialect} SQL expert"
                            ),
                            HumanPromptTemplate.from_template(
                                "Please write a {dialect} SQL count the length of a field"
                            ),
                        ],
                    )
                )

            single_input = {"data": {"dialect": "mysql"}}
            single_expected_messages = [
                ModelMessage(
                    content="Please write a mysql SQL count the length of a field",
                    role="human",
                )
            ]
            with_sys_expected_messages = [
                ModelMessage(content="You are a mysql SQL expert", role="system"),
                ModelMessage(
                    content="Please write a mysql SQL count the length of a field",
                    role="human",
                ),
            ]
            assert (
                asyncio.run(str_prompt.call(call_data=single_input))
                == single_expected_messages
            )
            assert (
                asyncio.run(tp_prompt.call(call_data=single_input))
                == single_expected_messages
            )
            assert (
                asyncio.run(chat_prompt.call(call_data=single_input))
                == single_expected_messages
            )
            assert (
                asyncio.run(with_sys_prompt.call(call_data=single_input))
                == with_sys_expected_messages
            )

    """

    def __init__(self, prompt: PromptTemplateType, **kwargs):
        if isinstance(prompt, str):
            prompt = ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template(prompt)]
            )
        elif isinstance(prompt, BasePromptTemplate) and not isinstance(
            prompt, ChatPromptTemplate
        ):
            prompt = ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template(prompt.template)]
            )
        elif isinstance(prompt, MessageType):
            prompt = ChatPromptTemplate(messages=[prompt])
        self._prompt = prompt

        super().__init__(check_storage=False, **kwargs)
        MapOperator.__init__(self, map_function=self.merge_prompt, **kwargs)

    @rearrange_args_by_type
    async def merge_prompt(self, prompt_dict: Dict[str, Any]) -> List[ModelMessage]:
        return await self.format_prompt(self._prompt, prompt_dict)


class DynamicPromptBuilderOperator(
    BasePromptBuilderOperator, JoinOperator[List[ModelMessage]]
):
    """The operator to build the prompt with dynamic prompt.

    The prompt template is dynamic, and it created by parent operator.
    """

    def __init__(self, **kwargs):
        super().__init__(check_storage=False, **kwargs)
        JoinOperator.__init__(self, combine_function=self.merge_prompt, **kwargs)

    @rearrange_args_by_type
    async def merge_prompt(
        self, prompt: ChatPromptTemplate, prompt_dict: Dict[str, Any]
    ) -> List[ModelMessage]:
        return await self.format_prompt(prompt, prompt_dict)


class HistoryPromptBuilderOperator(
    BasePromptBuilderOperator, JoinOperator[List[ModelMessage]]
):
    def __init__(
        self,
        prompt: ChatPromptTemplate,
        history_key: Optional[str] = None,
        check_storage: bool = True,
        str_history: bool = False,
        **kwargs,
    ):
        self._prompt = prompt
        self._history_key = history_key
        self._str_history = str_history
        BasePromptBuilderOperator.__init__(self, check_storage=check_storage)
        JoinOperator.__init__(self, combine_function=self.merge_history, **kwargs)

    @rearrange_args_by_type
    async def merge_history(
        self, history: List[BaseMessage], prompt_dict: Dict[str, Any]
    ) -> List[ModelMessage]:
        if self._str_history:
            prompt_dict[self._history_key] = BaseMessage.messages_to_string(history)
        else:
            prompt_dict[self._history_key] = history
        return await self.format_prompt(self._prompt, prompt_dict)


class HistoryDynamicPromptBuilderOperator(
    BasePromptBuilderOperator, JoinOperator[List[ModelMessage]]
):
    """The operator to build the prompt with dynamic prompt.

    The prompt template is dynamic, and it created by parent operator.
    """

    def __init__(
        self,
        history_key: Optional[str] = None,
        check_storage: bool = True,
        str_history: bool = False,
        **kwargs,
    ):
        self._history_key = history_key
        self._str_history = str_history
        BasePromptBuilderOperator.__init__(self, check_storage=check_storage)
        JoinOperator.__init__(self, combine_function=self.merge_history, **kwargs)

    @rearrange_args_by_type
    async def merge_history(
        self,
        prompt: ChatPromptTemplate,
        history: List[BaseMessage],
        prompt_dict: Dict[str, Any],
    ) -> List[ModelMessage]:
        if self._str_history:
            prompt_dict[self._history_key] = BaseMessage.messages_to_string(history)
        else:
            prompt_dict[self._history_key] = history
        return await self.format_prompt(prompt, prompt_dict)
