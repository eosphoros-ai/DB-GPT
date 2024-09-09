from typing import List, Literal, Optional, Tuple, Union, cast

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import (
    BaseMessage,
    ChatPromptTemplate,
    LLMClient,
    ModelOutput,
    ModelRequest,
    StorageConversation,
)
from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    CommonLLMHttpRequestBody,
    DAGContext,
    DefaultInputContext,
    InputOperator,
    JoinOperator,
    MapOperator,
    SimpleCallDataInputSource,
    TaskOutput,
)
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    ViewMetadata,
    ui,
)
from dbgpt.core.interface.operators.message_operator import (
    BaseConversationOperator,
    BufferedConversationMapperOperator,
    TokenBufferedConversationMapperOperator,
)
from dbgpt.core.interface.operators.prompt_operator import HistoryPromptBuilderOperator
from dbgpt.model.operators import LLMOperator, StreamingLLMOperator
from dbgpt.serve.conversation.serve import Serve as ConversationServe
from dbgpt.util.i18n_utils import _
from dbgpt.util.tracer import root_tracer


class HOContextBody(BaseModel):
    """Higher-order context body."""

    context_key: str = Field(
        "context",
        description=_("The context key can be used as the key for formatting prompt."),
    )
    context: Union[str, List[str]] = Field(
        ...,
        description=_("The context."),
    )


class BaseHOLLMOperator(
    BaseConversationOperator,
    JoinOperator[ModelRequest],
    LLMOperator,
    StreamingLLMOperator,
):
    """Higher-order model request builder operator."""

    def __init__(
        self,
        prompt_template: ChatPromptTemplate,
        model: str = None,
        llm_client: Optional[LLMClient] = None,
        history_merge_mode: Literal["none", "window", "token"] = "window",
        user_message_key: str = "user_input",
        history_key: Optional[str] = None,
        keep_start_rounds: Optional[int] = None,
        keep_end_rounds: Optional[int] = None,
        max_token_limit: int = 2048,
        **kwargs,
    ):
        JoinOperator.__init__(self, combine_function=self._join_func, **kwargs)
        LLMOperator.__init__(self, llm_client=llm_client, **kwargs)
        StreamingLLMOperator.__init__(self, llm_client=llm_client, **kwargs)

        # User must select a history merge mode
        self._history_merge_mode = history_merge_mode
        self._user_message_key = user_message_key
        self._has_history = history_merge_mode != "none"
        self._prompt_template = prompt_template
        self._model = model
        self._history_key = history_key
        self._str_history = False
        self._keep_start_rounds = keep_start_rounds if self._has_history else 0
        self._keep_end_rounds = keep_end_rounds if self._has_history else 0
        self._max_token_limit = max_token_limit
        self._sub_compose_dag: Optional[DAG] = None

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[ModelOutput]:
        conv_serve = ConversationServe.get_instance(self.system_app)
        self._storage = conv_serve.conv_storage
        self._message_storage = conv_serve.message_storage

        _: TaskOutput[ModelRequest] = await JoinOperator._do_run(self, dag_ctx)
        dag_ctx.current_task_context.set_task_input(
            DefaultInputContext([dag_ctx.current_task_context])
        )
        if dag_ctx.streaming_call:
            task_output = await StreamingLLMOperator._do_run(self, dag_ctx)
        else:
            task_output = await LLMOperator._do_run(self, dag_ctx)

        return task_output

    async def after_dag_end(self, event_loop_task_id: int):
        model_output: Optional[
            ModelOutput
        ] = await self.current_dag_context.get_from_share_data(
            LLMOperator.SHARE_DATA_KEY_MODEL_OUTPUT
        )
        model_output_view: Optional[
            str
        ] = await self.current_dag_context.get_from_share_data(
            LLMOperator.SHARE_DATA_KEY_MODEL_OUTPUT_VIEW
        )
        storage_conv = await self.get_storage_conversation()
        end_current_round: bool = False
        if model_output and storage_conv:
            # Save model output message to storage
            storage_conv.add_ai_message(model_output.text)
            end_current_round = True
        if model_output_view and storage_conv:
            # Save model output view to storage
            storage_conv.add_view_message(model_output_view)
            end_current_round = True
        if end_current_round:
            # End current conversation round and flush to storage
            storage_conv.end_current_round()

    async def _join_func(self, req: CommonLLMHttpRequestBody, *args):
        dynamic_inputs = []
        for arg in args:
            if isinstance(arg, HOContextBody):
                dynamic_inputs.append(arg)
        # Load and store chat history, default use InMemoryStorage.
        storage_conv, history_messages = await self.blocking_func_to_async(
            self._build_storage, req
        )
        # Save the storage conversation to share data, for the child operators
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_STORAGE_CONVERSATION, storage_conv
        )

        user_input = (
            req.messages[-1] if isinstance(req.messages, list) else req.messages
        )
        prompt_dict = {
            self._user_message_key: user_input,
        }
        for dynamic_input in dynamic_inputs:
            if dynamic_input.context_key in prompt_dict:
                raise ValueError(
                    f"Duplicate context key '{dynamic_input.context_key}' in upstream "
                    f"operators."
                )
            prompt_dict[dynamic_input.context_key] = dynamic_input.context

        call_data = {
            "messages": history_messages,
            "prompt_dict": prompt_dict,
        }
        end_node: BaseOperator = cast(BaseOperator, self.sub_compose_dag.leaf_nodes[0])
        # Sub dag, use the same dag context in the parent dag
        messages = await end_node.call(call_data, dag_ctx=self.current_dag_context)
        model_request = ModelRequest.build_request(
            model=req.model,
            messages=messages,
            context=req.context,
            temperature=req.temperature,
            max_new_tokens=req.max_new_tokens,
            span_id=root_tracer.get_current_span_id(),
            echo=False,
        )
        if storage_conv:
            # Start new round
            storage_conv.start_new_round()
            storage_conv.add_user_message(user_input)
        return model_request

    @property
    def sub_compose_dag(self) -> DAG:
        if not self._sub_compose_dag:
            self._sub_compose_dag = self._build_conversation_composer_dag()
        return self._sub_compose_dag

    def _build_storage(
        self, req: CommonLLMHttpRequestBody
    ) -> Tuple[StorageConversation, List[BaseMessage]]:
        # Create a new storage conversation, this will load the conversation from
        # storage, so we must do this async
        storage_conv: StorageConversation = StorageConversation(
            conv_uid=req.conv_uid,
            chat_mode=req.chat_mode,
            user_name=req.user_name,
            sys_code=req.sys_code,
            conv_storage=self.storage,
            message_storage=self.message_storage,
            param_type="",
            param_value=req.chat_param,
        )
        # Get history messages from storage
        history_messages: List[BaseMessage] = storage_conv.get_history_message(
            include_system_message=False
        )

        return storage_conv, history_messages

    def _build_conversation_composer_dag(self) -> DAG:
        default_dag_variables = self.dag._default_dag_variables if self.dag else None
        with DAG(
            "dbgpt_awel_app_chat_history_prompt_composer",
            default_dag_variables=default_dag_variables,
        ) as composer_dag:
            input_task = InputOperator(input_source=SimpleCallDataInputSource())
            # History transform task
            if self._history_merge_mode == "token":
                history_transform_task = TokenBufferedConversationMapperOperator(
                    model=self._model,
                    llm_client=self.llm_client,
                    max_token_limit=self._max_token_limit,
                )
            else:
                history_transform_task = BufferedConversationMapperOperator(
                    keep_start_rounds=self._keep_start_rounds,
                    keep_end_rounds=self._keep_end_rounds,
                )
            if self._history_key:
                history_key = self._history_key
            else:
                placeholders = self._prompt_template.get_placeholders()
                if not placeholders or len(placeholders) != 1:
                    raise ValueError(
                        "The prompt template must have exactly one placeholder if "
                        "history_key is not provided."
                    )
                history_key = placeholders[0]
            history_prompt_build_task = HistoryPromptBuilderOperator(
                prompt=self._prompt_template,
                history_key=history_key,
                check_storage=False,
                save_to_storage=False,
                str_history=self._str_history,
            )
            # Build composer dag
            (
                input_task
                >> MapOperator(lambda x: x["messages"])
                >> history_transform_task
                >> history_prompt_build_task
            )
            (
                input_task
                >> MapOperator(lambda x: x["prompt_dict"])
                >> history_prompt_build_task
            )

        return composer_dag


_PARAMETER_PROMPT_TEMPLATE = Parameter.build_from(
    _("Prompt Template"),
    "prompt_template",
    ChatPromptTemplate,
    description=_("The prompt template for the conversation."),
)
_PARAMETER_MODEL = Parameter.build_from(
    _("Model Name"),
    "model",
    str,
    optional=True,
    default=None,
    description=_("The model name."),
)

_PARAMETER_LLM_CLIENT = Parameter.build_from(
    _("LLM Client"),
    "llm_client",
    LLMClient,
    optional=True,
    default=None,
    description=_(
        "The LLM Client, how to connect to the LLM model, if not provided, it will use"
        " the default client deployed by DB-GPT."
    ),
)
_PARAMETER_HISTORY_MERGE_MODE = Parameter.build_from(
    _("History Message Merge Mode"),
    "history_merge_mode",
    str,
    optional=True,
    default="none",
    options=[
        OptionValue(label="No History", name="none", value="none"),
        OptionValue(label="Message Window", name="window", value="window"),
        OptionValue(label="Token Length", name="token", value="token"),
    ],
    description=_(
        "The history merge mode, supports 'none', 'window' and 'token'."
        " 'none': no history merge, 'window': merge by conversation window, 'token': "
        "merge by token length."
    ),
    ui=ui.UISelect(),
)
_PARAMETER_USER_MESSAGE_KEY = Parameter.build_from(
    _("User Message Key"),
    "user_message_key",
    str,
    optional=True,
    default="user_input",
    description=_(
        "The key of the user message in your prompt, default is 'user_input'."
    ),
)
_PARAMETER_HISTORY_KEY = Parameter.build_from(
    _("History Key"),
    "history_key",
    str,
    optional=True,
    default=None,
    description=_(
        "The chat history key, with chat history message pass to prompt template, "
        "if not provided, it will parse the prompt template to get the key."
    ),
)
_PARAMETER_KEEP_START_ROUNDS = Parameter.build_from(
    _("Keep Start Rounds"),
    "keep_start_rounds",
    int,
    optional=True,
    default=None,
    description=_("The start rounds to keep in the chat history."),
)
_PARAMETER_KEEP_END_ROUNDS = Parameter.build_from(
    _("Keep End Rounds"),
    "keep_end_rounds",
    int,
    optional=True,
    default=None,
    description=_("The end rounds to keep in the chat history."),
)
_PARAMETER_MAX_TOKEN_LIMIT = Parameter.build_from(
    _("Max Token Limit"),
    "max_token_limit",
    int,
    optional=True,
    default=2048,
    description=_("The max token limit to keep in the chat history."),
)

_INPUTS_COMMON_LLM_REQUEST_BODY = IOField.build_from(
    _("Common LLM Request Body"),
    "common_llm_request_body",
    CommonLLMHttpRequestBody,
    _("The common LLM request body."),
)
_INPUTS_EXTRA_CONTEXT = IOField.build_from(
    _("Extra Context"),
    "extra_context",
    HOContextBody,
    _(
        "Extra context for building prompt(Knowledge context, database "
        "schema, etc), you can add multiple context."
    ),
    dynamic=True,
)
_OUTPUTS_MODEL_OUTPUT = IOField.build_from(
    _("Model Output"),
    "model_output",
    ModelOutput,
    description=_("The model output."),
)
_OUTPUTS_STREAMING_MODEL_OUTPUT = IOField.build_from(
    _("Streaming Model Output"),
    "streaming_model_output",
    ModelOutput,
    is_list=True,
    description=_("The streaming model output."),
)


class HOLLMOperator(BaseHOLLMOperator):
    metadata = ViewMetadata(
        label=_("LLM Operator"),
        name="higher_order_llm_operator",
        category=OperatorCategory.LLM,
        description=_(
            "High-level LLM operator, supports multi-round conversation "
            "(conversation window, token length and no multi-round)."
        ),
        parameters=[
            _PARAMETER_PROMPT_TEMPLATE.new(),
            _PARAMETER_MODEL.new(),
            _PARAMETER_LLM_CLIENT.new(),
            _PARAMETER_HISTORY_MERGE_MODE.new(),
            _PARAMETER_USER_MESSAGE_KEY.new(),
            _PARAMETER_HISTORY_KEY.new(),
            _PARAMETER_KEEP_START_ROUNDS.new(),
            _PARAMETER_KEEP_END_ROUNDS.new(),
            _PARAMETER_MAX_TOKEN_LIMIT.new(),
        ],
        inputs=[
            _INPUTS_COMMON_LLM_REQUEST_BODY.new(),
            _INPUTS_EXTRA_CONTEXT.new(),
        ],
        outputs=[
            _OUTPUTS_MODEL_OUTPUT.new(),
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class HOStreamingLLMOperator(BaseHOLLMOperator):
    metadata = ViewMetadata(
        label=_("Streaming LLM Operator"),
        name="higher_order_streaming_llm_operator",
        category=OperatorCategory.LLM,
        description=_(
            "High-level streaming LLM operator, supports multi-round conversation "
            "(conversation window, token length and no multi-round)."
        ),
        parameters=[
            _PARAMETER_PROMPT_TEMPLATE.new(),
            _PARAMETER_MODEL.new(),
            _PARAMETER_LLM_CLIENT.new(),
            _PARAMETER_HISTORY_MERGE_MODE.new(),
            _PARAMETER_USER_MESSAGE_KEY.new(),
            _PARAMETER_HISTORY_KEY.new(),
            _PARAMETER_KEEP_START_ROUNDS.new(),
            _PARAMETER_KEEP_END_ROUNDS.new(),
            _PARAMETER_MAX_TOKEN_LIMIT.new(),
        ],
        inputs=[
            _INPUTS_COMMON_LLM_REQUEST_BODY.new(),
            _INPUTS_EXTRA_CONTEXT.new(),
        ],
        outputs=[
            _OUTPUTS_STREAMING_MODEL_OUTPUT.new(),
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
