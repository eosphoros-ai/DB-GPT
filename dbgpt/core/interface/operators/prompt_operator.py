"""The prompt operator."""

from abc import ABC
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import model_validator
from dbgpt.core import ModelMessage, ModelOutput, StorageConversation
from dbgpt.core.awel import JoinOperator, MapOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    OperatorType,
    Parameter,
    ResourceCategory,
    ViewMetadata,
    register_resource,
    ui,
)
from dbgpt.core.interface.message import BaseMessage
from dbgpt.core.interface.operators.llm_operator import BaseLLM
from dbgpt.core.interface.operators.message_operator import BaseConversationOperator
from dbgpt.core.interface.prompt import (
    BaseChatPromptTemplate,
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    MessageType,
    PromptTemplate,
    SystemPromptTemplate,
)
from dbgpt.util.function_utils import rearrange_args_by_type
from dbgpt.util.i18n_utils import _


@register_resource(
    label=_("Common Chat Prompt Template"),
    name="common_chat_prompt_template",
    category=ResourceCategory.PROMPT,
    description=_("The operator to build the prompt with static prompt."),
    tags={"order": TAGS_ORDER_HIGH},
    parameters=[
        Parameter.build_from(
            label=_("System Message"),
            name="system_message",
            type=str,
            optional=True,
            default="You are a helpful AI Assistant.",
            description=_("The system message."),
            ui=ui.DefaultUITextArea(),
        ),
        Parameter.build_from(
            label=_("Message placeholder"),
            name="message_placeholder",
            type=str,
            optional=True,
            default="chat_history",
            description=_("The chat history message placeholder."),
        ),
        Parameter.build_from(
            label=_("Human Message"),
            name="human_message",
            type=str,
            optional=True,
            default="{user_input}",
            placeholder="{user_input}",
            description=_("The human message."),
            ui=ui.DefaultUITextArea(),
        ),
    ],
)
class CommonChatPromptTemplate(ChatPromptTemplate):
    """The common chat prompt template."""

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the messages."""
        if not isinstance(values, dict):
            return values
        if "system_message" not in values:
            values["system_message"] = "You are a helpful AI Assistant."
        if "human_message" not in values:
            values["human_message"] = "{user_input}"
        if "message_placeholder" not in values:
            values["message_placeholder"] = "chat_history"
        system_message = values.pop("system_message")
        human_message = values.pop("human_message")
        message_placeholder = values.pop("message_placeholder")
        values["messages"] = [
            SystemPromptTemplate.from_template(system_message),
            MessagesPlaceholder(variable_name=message_placeholder),
            HumanPromptTemplate.from_template(human_message),
        ]
        return cls.base_pre_fill(values)


class BasePromptBuilderOperator(BaseConversationOperator, ABC):
    """The base prompt builder operator."""

    def __init__(self, check_storage: bool, save_to_storage: bool = True, **kwargs):
        """Create a new prompt builder operator."""
        super().__init__(check_storage=check_storage, **kwargs)
        self._save_to_storage = save_to_storage

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
        model_messages = ModelMessage.from_base_messages(messages)
        if self._save_to_storage:
            # Start new round conversation, and save user message to storage
            await self.start_new_round_conv(model_messages)
        return model_messages

    async def start_new_round_conv(self, messages: List[ModelMessage]) -> None:
        """Start a new round conversation.

        Args:
            messages (List[ModelMessage]): The messages.
        """
        lass_user_message = ModelMessage.parse_user_message(messages)
        storage_conv: Optional[
            StorageConversation
        ] = await self.get_storage_conversation()
        if not storage_conv:
            return
        # Start new round
        storage_conv.start_new_round()
        storage_conv.add_user_message(lass_user_message)

    async def after_dag_end(self, event_loop_task_id: int):
        """Execute after the DAG finished."""
        if not self._save_to_storage:
            return
        # Save the storage conversation to storage after the whole DAG finished
        storage_conv: Optional[
            StorageConversation
        ] = await self.get_storage_conversation()

        if not storage_conv:
            return
        model_output: Optional[
            ModelOutput
        ] = await self.current_dag_context.get_from_share_data(
            BaseLLM.SHARE_DATA_KEY_MODEL_OUTPUT
        )
        if model_output:
            # Save model output message to storage
            storage_conv.add_ai_message(model_output.text)
            # End current conversation round and flush to storage
            storage_conv.end_current_round()


PromptTemplateType = Union[ChatPromptTemplate, PromptTemplate, MessageType, str]


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
            from dbgpt.core.operators import PromptBuilderOperator

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
                                "Please write a {dialect} SQL count the length of a"
                                " field"
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
                                "Please write a {dialect} SQL count the length of a"
                                " field"
                            ),
                        ],
                    )
                )

            single_input = {"dialect": "mysql"}
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

    metadata = ViewMetadata(
        label=_("Prompt Builder Operator"),
        name="prompt_builder_operator",
        description=_("Build messages from prompt template."),
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(
                _("Chat Prompt Template"),
                "prompt",
                ChatPromptTemplate,
                description=_("The chat prompt template."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Prompt Input Dict"),
                "prompt_input_dict",
                dict,
                description=_("The prompt dict."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Formatted Messages"),
                "formatted_messages",
                ModelMessage,
                is_list=True,
                description=_("The formatted messages."),
            )
        ],
    )

    def __init__(self, prompt: PromptTemplateType, **kwargs):
        """Create a new prompt builder operator."""
        if isinstance(prompt, str):
            prompt = ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template(prompt)]
            )
        elif isinstance(prompt, PromptTemplate):
            prompt = ChatPromptTemplate(
                messages=[HumanPromptTemplate.from_template(prompt.template)]
            )
        elif isinstance(
            prompt, (BaseChatPromptTemplate, MessagesPlaceholder, BaseMessage)
        ):
            prompt = ChatPromptTemplate(messages=[prompt])
        self._prompt = prompt

        super().__init__(check_storage=False, **kwargs)
        MapOperator.__init__(self, map_function=self.merge_prompt, **kwargs)

    @rearrange_args_by_type
    async def merge_prompt(self, prompt_dict: Dict[str, Any]) -> List[ModelMessage]:
        """Format the prompt."""
        return await self.format_prompt(self._prompt, prompt_dict)


class DynamicPromptBuilderOperator(
    BasePromptBuilderOperator, JoinOperator[List[ModelMessage]]
):
    """The operator to build the prompt with dynamic prompt.

    The prompt template is dynamic, and it created by parent operator.
    """

    def __init__(self, **kwargs):
        """Create a new dynamic prompt builder operator."""
        super().__init__(check_storage=False, **kwargs)
        JoinOperator.__init__(self, combine_function=self.merge_prompt, **kwargs)

    @rearrange_args_by_type
    async def merge_prompt(
        self, prompt: ChatPromptTemplate, prompt_dict: Dict[str, Any]
    ) -> List[ModelMessage]:
        """Merge the prompt and history."""
        return await self.format_prompt(prompt, prompt_dict)


class HistoryPromptBuilderOperator(
    BasePromptBuilderOperator, JoinOperator[List[ModelMessage]]
):
    """The operator to build the prompt with static prompt.

    The prompt will pass to this operator.
    """

    metadata = ViewMetadata(
        label=_("History Prompt Builder Operator"),
        name="history_prompt_builder_operator",
        description=_("Build messages from prompt template and chat history."),
        operator_type=OperatorType.JOIN,
        category=OperatorCategory.CONVERSION,
        parameters=[
            Parameter.build_from(
                _("Chat Prompt Template"),
                "prompt",
                ChatPromptTemplate,
                description=_("The chat prompt template."),
            ),
            Parameter.build_from(
                _("History Key"),
                "history_key",
                str,
                optional=True,
                default="chat_history",
                description=_("The key of history in prompt dict."),
            ),
            Parameter.build_from(
                _("String History"),
                "str_history",
                bool,
                optional=True,
                default=False,
                description=_("Whether to convert the history to string."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("History"),
                "history",
                BaseMessage,
                is_list=True,
                description=_("The history."),
            ),
            IOField.build_from(
                _("Prompt Input Dict"),
                "prompt_input_dict",
                dict,
                description=_("The prompt dict."),
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Formatted Messages"),
                "formatted_messages",
                ModelMessage,
                is_list=True,
                description=_("The formatted messages."),
            )
        ],
    )

    def __init__(
        self,
        prompt: ChatPromptTemplate,
        history_key: str = "chat_history",
        check_storage: bool = True,
        str_history: bool = False,
        **kwargs,
    ):
        """Create a new history prompt builder operator.

        Args:
            prompt (ChatPromptTemplate): The prompt.
            history_key (str, optional): The key of history in prompt dict. Defaults
                to "chat_history".
            check_storage (bool, optional): Whether to check the storage.
                Defaults to True.
            str_history (bool, optional): Whether to convert the history to string.
                Defaults to False.
        """
        self._prompt = prompt
        self._history_key = history_key
        self._str_history = str_history
        BasePromptBuilderOperator.__init__(self, check_storage=check_storage, **kwargs)
        JoinOperator.__init__(self, combine_function=self.merge_history, **kwargs)

    @rearrange_args_by_type
    async def merge_history(
        self, history: List[BaseMessage], prompt_dict: Dict[str, Any]
    ) -> List[ModelMessage]:
        """Merge the prompt and history."""
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
        history_key: str = "chat_history",
        check_storage: bool = True,
        str_history: bool = False,
        **kwargs,
    ):
        """Create a new history dynamic prompt builder operator."""
        self._history_key = history_key
        self._str_history = str_history
        BasePromptBuilderOperator.__init__(self, check_storage=check_storage, **kwargs)
        JoinOperator.__init__(self, combine_function=self.merge_history, **kwargs)

    @rearrange_args_by_type
    async def merge_history(
        self,
        prompt: ChatPromptTemplate,
        history: List[BaseMessage],
        prompt_dict: Dict[str, Any],
    ) -> List[ModelMessage]:
        """Merge the prompt and history."""
        if self._str_history:
            prompt_dict[self._history_key] = BaseMessage.messages_to_string(history)
        else:
            prompt_dict[self._history_key] = history
        return await self.format_prompt(prompt, prompt_dict)
