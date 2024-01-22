import dataclasses
from typing import Any, Dict, List, Optional

from dbgpt import SystemApp
from dbgpt.component import ComponentType
from dbgpt.core import (
    BaseMessage,
    ChatPromptTemplate,
    LLMClient,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    InputOperator,
    JoinOperator,
    MapOperator,
    SimpleCallDataInputSource,
)
from dbgpt.core.operators import (
    BufferedConversationMapperOperator,
    HistoryPromptBuilderOperator,
    LLMBranchOperator,
)
from dbgpt.model.operators import LLMOperator, StreamingLLMOperator
from dbgpt.storage.cache.operator import (
    CachedModelOperator,
    CachedModelStreamOperator,
    CacheManager,
    ModelCacheBranchOperator,
    ModelSaveCacheOperator,
    ModelStreamSaveCacheOperator,
)


@dataclasses.dataclass
class ChatComposerInput:
    """The composer input."""

    messages: List[BaseMessage]
    prompt_dict: Dict[str, Any]


class AppChatComposerOperator(MapOperator[ChatComposerInput, ModelRequest]):
    """App chat composer operator.

    TODO: Support more history merge mode.
    """

    def __init__(
        self,
        model: str,
        temperature: float,
        max_new_tokens: int,
        prompt: ChatPromptTemplate,
        message_version: str = "v2",
        echo: bool = False,
        streaming: bool = True,
        history_key: str = "chat_history",
        history_merge_mode: str = "window",
        keep_start_rounds: Optional[int] = None,
        keep_end_rounds: Optional[int] = None,
        str_history: bool = False,
        request_context: ModelRequestContext = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if not request_context:
            request_context = ModelRequestContext(stream=streaming)
        self._prompt_template = prompt
        self._history_key = history_key
        self._history_merge_mode = history_merge_mode
        self._keep_start_rounds = keep_start_rounds
        self._keep_end_rounds = keep_end_rounds
        self._str_history = str_history
        self._model_name = model
        self._temperature = temperature
        self._max_new_tokens = max_new_tokens
        self._message_version = message_version
        self._echo = echo
        self._streaming = streaming
        self._request_context = request_context
        self._sub_compose_dag = self._build_composer_dag()

    async def map(self, input_value: ChatComposerInput) -> ModelRequest:
        end_node: BaseOperator = self._sub_compose_dag.leaf_nodes[0]
        # Sub dag, use the same dag context in the parent dag
        messages = await end_node.call(
            call_data=input_value, dag_ctx=self.current_dag_context
        )
        span_id = self._request_context.span_id
        model_request = ModelRequest.build_request(
            model=self._model_name,
            messages=messages,
            context=self._request_context,
            temperature=self._temperature,
            max_new_tokens=self._max_new_tokens,
            span_id=span_id,
            echo=self._echo,
        )
        return model_request

    def _build_composer_dag(self) -> DAG:
        with DAG("dbgpt_awel_app_chat_history_prompt_composer") as composer_dag:
            input_task = InputOperator(input_source=SimpleCallDataInputSource())
            # History transform task
            history_transform_task = BufferedConversationMapperOperator(
                keep_start_rounds=self._keep_start_rounds,
                keep_end_rounds=self._keep_end_rounds,
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


def build_cached_chat_operator(
    llm_client: LLMClient,
    is_streaming: bool,
    system_app: SystemApp,
    cache_manager: Optional[CacheManager] = None,
):
    """Builds and returns a model processing workflow (DAG) operator.

    This function constructs a Directed Acyclic Graph (DAG) for processing data using a model.
    It includes caching and branching logic to either fetch results from a cache or process
    data using the model. It supports both streaming and non-streaming modes.

    .. code-block:: python

        input_task >> cache_check_branch_task
        cache_check_branch_task >> llm_task >> save_cache_task >> join_task
        cache_check_branch_task >> cache_task >> join_task

    equivalent to::

                          -> llm_task -> save_cache_task ->
                         /                                    \
        input_task -> cache_check_branch_task                   ---> join_task
                        \                                     /
                         -> cache_task ------------------- ->

    Args:
        llm_client (LLMClient): The LLM client for processing data using the model.
        is_streaming (bool): Whether the model is a streaming model.
        system_app (SystemApp): The system app.
        cache_manager (CacheManager, optional): The cache manager for managing cache operations. Defaults to None.

    Returns:
        BaseOperator: The final operator in the constructed DAG, typically a join node.
    """
    # Define task names for the model and cache nodes
    model_task_name = "llm_model_node"
    cache_task_name = "llm_model_cache_node"
    if not cache_manager:
        cache_manager: CacheManager = system_app.get_component(
            ComponentType.MODEL_CACHE_MANAGER, CacheManager
        )

    with DAG("dbgpt_awel_app_model_infer_with_cached") as dag:
        # Create an input task
        input_task = InputOperator(SimpleCallDataInputSource())
        # Create a branch task to decide between fetching from cache or processing with the model
        if is_streaming:
            llm_task = StreamingLLMOperator(llm_client, task_name=model_task_name)
            cache_task = CachedModelStreamOperator(
                cache_manager, task_name=cache_task_name
            )
            save_cache_task = ModelStreamSaveCacheOperator(cache_manager)
        else:
            llm_task = LLMOperator(llm_client, task_name=model_task_name)
            cache_task = CachedModelOperator(cache_manager, task_name=cache_task_name)
            save_cache_task = ModelSaveCacheOperator(cache_manager)

        # Create a branch node to decide between fetching from cache or processing with the model
        cache_check_branch_task = ModelCacheBranchOperator(
            cache_manager,
            model_task_name=model_task_name,
            cache_task_name=cache_task_name,
        )
        # Create a join node to merge outputs from the model and cache nodes, just keep the first not empty output
        join_task = JoinOperator(
            combine_function=lambda model_out, cache_out: cache_out or model_out
        )

        # Define the workflow structure using the >> operator
        input_task >> cache_check_branch_task
        cache_check_branch_task >> llm_task >> save_cache_task >> join_task
        cache_check_branch_task >> cache_task >> join_task
        return join_task
