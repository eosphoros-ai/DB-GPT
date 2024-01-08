import dataclasses
from typing import Any, Dict, List, Optional

from dbgpt.core import (
    ChatPromptTemplate,
    MessageStorageItem,
    ModelMessage,
    ModelRequest,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    InputOperator,
    JoinOperator,
    MapOperator,
    SimpleCallDataInputSource,
)
from dbgpt.core.interface.operator.prompt_operator import HistoryPromptBuilderOperator

from .message_operator import (
    BufferedConversationMapperOperator,
    ChatHistoryLoadType,
    PreChatHistoryLoadOperator,
)


@dataclasses.dataclass
class ChatComposerInput:
    """The composer input."""

    prompt_dict: Dict[str, Any]
    model_dict: Dict[str, Any]
    context: ChatHistoryLoadType


class ChatHistoryPromptComposerOperator(MapOperator[ChatComposerInput, ModelRequest]):
    """The chat history prompt composer operator.

    For simple use, you can use this operator to compose the chat history prompt.
    """

    def __init__(
        self,
        prompt_template: ChatPromptTemplate,
        history_key: str = "chat_history",
        last_k_round: int = 2,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._prompt_template = prompt_template
        self._history_key = history_key
        self._last_k_round = last_k_round
        self._storage = storage
        self._message_storage = message_storage
        self._sub_compose_dag = self._build_composer_dag()

    async def map(self, input_value: ChatComposerInput) -> ModelRequest:
        end_node: BaseOperator = self._sub_compose_dag.leaf_nodes[0]
        # Sub dag, use the same dag context in the parent dag
        return await end_node.call(
            call_data={"data": input_value}, dag_ctx=self.current_dag_context
        )

    def _build_composer_dag(self) -> DAG:
        with DAG("dbgpt_awel_chat_history_prompt_composer") as composer_dag:
            input_task = InputOperator(input_source=SimpleCallDataInputSource())
            # Load and store chat history, default use InMemoryStorage.
            chat_history_load_task = PreChatHistoryLoadOperator(
                storage=self._storage, message_storage=self._message_storage
            )
            # History transform task, here we keep last 5 round messages
            history_transform_task = BufferedConversationMapperOperator(
                last_k_round=self._last_k_round
            )
            history_prompt_build_task = HistoryPromptBuilderOperator(
                prompt=self._prompt_template, history_key=self._history_key
            )
            model_request_build_task = JoinOperator(self._build_model_request)

            # Build composer dag
            (
                input_task
                >> MapOperator(lambda x: x.context)
                >> chat_history_load_task
                >> history_transform_task
                >> history_prompt_build_task
            )
            (
                input_task
                >> MapOperator(lambda x: x.prompt_dict)
                >> history_prompt_build_task
            )

            history_prompt_build_task >> model_request_build_task
            (
                input_task
                >> MapOperator(lambda x: x.model_dict)
                >> model_request_build_task
            )

        return composer_dag

    def _build_model_request(
        self, messages: List[ModelMessage], model_dict: Dict[str, Any]
    ) -> ModelRequest:
        return ModelRequest.build_request(messages=messages, **model_dict)

    async def after_dag_end(self):
        # Should call after_dag_end() of sub dag
        await self._sub_compose_dag._after_dag_end()
