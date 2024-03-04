"""Composer operator for AWEL flow.

Usage cases: Some atomized operators cannot be easily modified on the flow page, we
need provide a way to compose the atomized operators to a new operator.
"""

from typing import Any, Dict, Optional, cast

from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    InputOperator,
    JoinOperator,
    MapOperator,
    SimpleCallDataInputSource,
)
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.core.awel.trigger.http_trigger import CommonLLMHttpRequestBody
from dbgpt.core.interface.llm import ModelRequest
from dbgpt.core.interface.message import MessageStorageItem, StorageConversation
from dbgpt.core.interface.operators.llm_operator import (
    MergedRequestBuilderOperator,
    RequestBuilderOperator,
)
from dbgpt.core.interface.operators.message_operator import (
    BufferedConversationMapperOperator,
    PreChatHistoryLoadOperator,
)
from dbgpt.core.interface.operators.prompt_operator import HistoryPromptBuilderOperator
from dbgpt.core.interface.prompt import ChatPromptTemplate
from dbgpt.core.interface.storage import StorageInterface


class ConversationComposerOperator(MapOperator[CommonLLMHttpRequestBody, ModelRequest]):
    """A Composer operator for conversation.

    Build for AWEL Flow.
    """

    metadata = ViewMetadata(
        label="Conversation Composer Operator",
        name="conversation_composer_operator",
        category=OperatorCategory.CONVERSION,
        description="A composer operator for conversation.\nIncluding chat history "
        "handling, prompt composing, etc. Output is ModelRequest.",
        parameters=[
            Parameter.build_from(
                "Prompt Template",
                "prompt_template",
                ChatPromptTemplate,
                description="The prompt template for the conversation.",
            ),
            Parameter.build_from(
                "Human Message Key",
                "human_message_key",
                str,
                optional=True,
                default="user_input",
                description="The key for human message in the prompt format dict.",
            ),
            Parameter.build_from(
                "History Key",
                "history_key",
                str,
                optional=True,
                default="chat_history",
                description="The chat history key, with chat history message pass to "
                "prompt template.",
            ),
            Parameter.build_from(
                "Keep Start Rounds",
                "keep_start_rounds",
                int,
                optional=True,
                default=None,
                description="The start rounds to keep in the chat history.",
            ),
            Parameter.build_from(
                "Keep End Rounds",
                "keep_end_rounds",
                int,
                optional=True,
                default=10,
                description="The end rounds to keep in the chat history.",
            ),
            Parameter.build_from(
                "Conversation Storage",
                "storage",
                StorageInterface,
                optional=True,
                default=None,
                description="The conversation storage(Not include message detail).",
            ),
            Parameter.build_from(
                "Message Storage",
                "message_storage",
                StorageInterface,
                optional=True,
                default=None,
                description="The message storage.",
            ),
        ],
        inputs=[
            IOField.build_from(
                "Common LLM Http Request Body",
                "common_llm_http_request_body",
                CommonLLMHttpRequestBody,
                description="The common LLM http request body.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Model Request",
                "model_request",
                ModelRequest,
                description="The model request with chat history prompt.",
            )
        ],
    )

    def __init__(
        self,
        prompt_template: ChatPromptTemplate,
        human_message_key: str = "user_input",
        history_key: str = "chat_history",
        keep_start_rounds: Optional[int] = None,
        keep_end_rounds: Optional[int] = None,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs
    ):
        """Create a new instance of ConversationComposerOperator."""
        super().__init__(**kwargs)
        self._prompt_template = prompt_template
        self._human_message_key = human_message_key
        self._history_key = history_key
        self._keep_start_rounds = keep_start_rounds
        self._keep_end_rounds = keep_end_rounds
        self._storage = storage
        self._message_storage = message_storage
        self._sub_compose_dag = self._build_composer_dag()

    async def map(self, input_value: CommonLLMHttpRequestBody) -> ModelRequest:
        """Receive the common LLM http request body, and build the model request."""
        end_node: BaseOperator = cast(BaseOperator, self._sub_compose_dag.leaf_nodes[0])
        # Sub dag, use the same dag context in the parent dag
        return await end_node.call(
            call_data=input_value, dag_ctx=self.current_dag_context
        )

    def _build_composer_dag(self):
        with DAG("dbgpt_awel_chat_history_prompt_composer") as composer_dag:
            input_task = InputOperator(input_source=SimpleCallDataInputSource())
            # Load and store chat history, default use InMemoryStorage.
            chat_history_load_task = PreChatHistoryLoadOperator(
                storage=self._storage, message_storage=self._message_storage
            )
            # History transform task, here we keep last 5 round messages
            history_transform_task = BufferedConversationMapperOperator(
                keep_start_rounds=self._keep_start_rounds,
                keep_end_rounds=self._keep_end_rounds,
            )
            history_prompt_build_task = HistoryPromptBuilderOperator(
                prompt=self._prompt_template, history_key=self._history_key
            )
            prompt_build_task = PromptFormatDictBuilderOperator(
                human_message_key=self._human_message_key
            )
            model_request_build_task: JoinOperator[
                ModelRequest
            ] = MergedRequestBuilderOperator()

            # Build composer dag
            (
                input_task
                >> MapOperator(lambda x: x.context)
                >> chat_history_load_task
                >> history_transform_task
                >> history_prompt_build_task
            )
            input_task >> prompt_build_task >> history_prompt_build_task

            input_task >> RequestBuilderOperator() >> model_request_build_task
            history_prompt_build_task >> model_request_build_task
        return composer_dag

    async def after_dag_end(self):
        """Execute after dag end."""
        # Should call after_dag_end() of sub dag
        await self._sub_compose_dag._after_dag_end()


class PromptFormatDictBuilderOperator(
    MapOperator[CommonLLMHttpRequestBody, Dict[str, Any]]
):
    """Prompt format dict builder operator for AWEL flow.

    Receive the common LLM http request body, and build the prompt format dict.
    """

    metadata = ViewMetadata(
        label="Prompt Format Dict Builder Operator",
        name="prompt_format_dict_builder_operator",
        category=OperatorCategory.CONVERSION,
        description="A operator to build prompt format dict from common LLM http "
        "request body.",
        parameters=[
            Parameter.build_from(
                "Human Message Key",
                "human_message_key",
                str,
                optional=True,
                default="user_input",
                description="The key for human message in the prompt format dict.",
            )
        ],
        inputs=[
            IOField.build_from(
                "Common LLM Http Request Body",
                "common_llm_http_request_body",
                CommonLLMHttpRequestBody,
                description="The common LLM http request body.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Prompt Format Dict",
                "prompt_format_dict",
                Dict[str, Any],
                description="The prompt format dict.",
            )
        ],
    )

    def __init__(self, human_message_key: str = "user_input", **kwargs):
        """Create a new instance of PromptFormatDictBuilderOperator."""
        self._human_message_key = human_message_key
        super().__init__(**kwargs)

    async def map(self, input_value: CommonLLMHttpRequestBody) -> Dict[str, Any]:
        """Build prompt format dict from common LLM http request body."""
        extra_data = input_value.context.extra if input_value.context.extra else {}
        return {
            self._human_message_key: input_value.messages,
            **extra_data,
        }
