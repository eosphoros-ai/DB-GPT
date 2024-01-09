import dataclasses
from typing import Any, Dict, List

from dbgpt.core import BaseMessage, ChatPromptTemplate, ModelMessage
from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    InputOperator,
    MapOperator,
    SimpleCallDataInputSource,
)
from dbgpt.core.operator import (
    BufferedConversationMapperOperator,
    HistoryPromptBuilderOperator,
)


@dataclasses.dataclass
class ChatComposerInput:
    """The composer input."""

    messages: List[BaseMessage]
    prompt_dict: Dict[str, Any]


class AppChatComposerOperator(MapOperator[ChatComposerInput, List[ModelMessage]]):
    """App chat composer operator.

    TODO: Support history merge mode.
    """

    def __init__(
        self,
        prompt: ChatPromptTemplate,
        history_key: str = "chat_history",
        history_merge_mode: str = "window",
        last_k_round: int = 2,
        str_history: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._prompt_template = prompt
        self._history_key = history_key
        self._history_merge_mode = history_merge_mode
        self._last_k_round = last_k_round
        self._str_history = str_history
        self._sub_compose_dag = self._build_composer_dag()

    async def map(self, input_value: ChatComposerInput) -> List[ModelMessage]:
        end_node: BaseOperator = self._sub_compose_dag.leaf_nodes[0]
        # Sub dag, use the same dag context in the parent dag
        return await end_node.call(
            call_data={"data": input_value}, dag_ctx=self.current_dag_context
        )

    def _build_composer_dag(self) -> DAG:
        with DAG("dbgpt_awel_app_chat_history_prompt_composer") as composer_dag:
            input_task = InputOperator(input_source=SimpleCallDataInputSource())
            # History transform task, here we keep last self._last_k_round round messages
            history_transform_task = BufferedConversationMapperOperator(
                last_k_round=self._last_k_round
            )
            history_prompt_build_task = HistoryPromptBuilderOperator(
                prompt=self._prompt_template,
                history_key=self._history_key,
                check_storage=False,
                str_history=self._str_history,
            )
            # Build composer dag
            (
                input_task
                >> MapOperator(lambda x: x.messages)
                >> history_transform_task
                >> history_prompt_build_task
            )
            (
                input_task
                >> MapOperator(lambda x: x.prompt_dict)
                >> history_prompt_build_task
            )

        return composer_dag
