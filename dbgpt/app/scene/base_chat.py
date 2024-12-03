import asyncio
import datetime
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict

from dbgpt._private.config import Config
from dbgpt._private.pydantic import EXTRA_FORBID
from dbgpt.app.scene.base import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.operators.app_operator import (
    AppChatComposerOperator,
    ChatComposerInput,
    build_cached_chat_operator,
)
from dbgpt.component import ComponentType
from dbgpt.core import LLMClient, ModelOutput, ModelRequest, ModelRequestContext
from dbgpt.core.interface.message import StorageConversation
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.serve.conversation.serve import Serve as ConversationServe
from dbgpt.util import get_or_create_event_loop
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.retry import async_retry
from dbgpt.util.tracer import root_tracer, trace

from .exceptions import BaseAppException

logger = logging.getLogger(__name__)
CFG = Config()


def _build_conversation(
    chat_mode: ChatScene,
    chat_param: Dict[str, Any],
    model_name: str,
    conv_serve: ConversationServe,
) -> StorageConversation:
    param_type = ""
    param_value = ""
    if chat_param["select_param"]:
        if len(chat_mode.param_types()) > 0:
            param_type = chat_mode.param_types()[0]
        param_value = chat_param["select_param"]
    return StorageConversation(
        chat_param["chat_session_id"],
        chat_mode=chat_mode.value(),
        user_name=chat_param.get("user_name"),
        sys_code=chat_param.get("sys_code"),
        model_name=model_name,
        param_type=param_type,
        param_value=param_value,
        conv_storage=conv_serve.conv_storage,
        message_storage=conv_serve.message_storage,
    )


class BaseChat(ABC):
    """DB-GPT Chat Service Base Module
    Include:
    stream_call():scene + prompt -> stream response
    nostream_call():scene + prompt -> nostream response
    """

    chat_scene: str = None
    llm_model: Any = None
    # By default, keep the last two rounds of conversation records as the context
    keep_start_rounds: int = 0
    keep_end_rounds: int = 0

    # Some model not support system role, this config is used to control whether to
    # convert system message to human message
    auto_convert_message: bool = True

    @trace("BaseChat.__init__")
    def __init__(self, chat_param: Dict):
        """Chat Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) select param
        """
        self.chat_session_id = chat_param["chat_session_id"]
        self.chat_mode = chat_param["chat_mode"]
        self.current_user_input: str = chat_param["current_user_input"]
        self.llm_model = (
            chat_param["model_name"] if chat_param["model_name"] else CFG.LLM_MODEL
        )
        self.llm_echo = False
        self.worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        self.model_cache_enable = chat_param.get("model_cache_enable", False)

        ### load prompt template
        # self.prompt_template: PromptTemplate = CFG.prompt_templates[
        #     self.chat_mode.value()
        # ]
        self.prompt_template: AppScenePromptTemplateAdapter = (
            CFG.prompt_template_registry.get_prompt_template(
                self.chat_mode.value(),
                language=CFG.LANGUAGE,
                model_name=self.llm_model,
                proxyllm_backend=CFG.PROXYLLM_BACKEND,
            )
        )
        self._conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
        # chat_history_fac = ChatHistory()
        ### can configurable storage methods
        # self.memory = chat_history_fac.get_store_instance(chat_param["chat_session_id"])

        # self.history_message: List[OnceConversation] = self.memory.messages()
        # self.current_message: OnceConversation = OnceConversation(
        #     self.chat_mode.value(),
        #     user_name=chat_param.get("user_name"),
        #     sys_code=chat_param.get("sys_code"),
        # )
        self.current_message: StorageConversation = _build_conversation(
            self.chat_mode, chat_param, self.llm_model, self._conv_serve
        )
        self.history_messages = self.current_message.get_history_message()
        self.current_tokens_used: int = 0
        # The executor to submit blocking function
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

        # self._model_operator: BaseOperator = _build_model_operator()
        # self._model_stream_operator: BaseOperator = _build_model_operator(
        #     is_stream=True, dag_name="llm_stream_model_dag"
        # )

        # In v1, we will transform the message to compatible format of specific model
        # In the future, we will upgrade the message version to v2, and the message will be compatible with all models
        self._message_version = chat_param.get("message_version", "v2")
        self._chat_param = chat_param

    @property
    def chat_type(self) -> str:
        raise NotImplementedError("Not supported for this chat type.")

    @abstractmethod
    async def generate_input_values(self) -> Dict:
        """Generate input to LLM

        Please note that you must not perform any blocking operations in this function

        Returns:
            a dictionary to be formatted by prompt template
        """

    @property
    def llm_client(self) -> LLMClient:
        """Return the LLM client."""
        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return DefaultLLMClient(
            worker_manager, auto_convert_message=self.auto_convert_message
        )

    async def call_llm_operator(self, request: ModelRequest) -> ModelOutput:
        llm_task = build_cached_chat_operator(self.llm_client, False, CFG.SYSTEM_APP)
        return await llm_task.call(call_data=request)

    async def call_streaming_operator(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelOutput]:
        llm_task = build_cached_chat_operator(self.llm_client, True, CFG.SYSTEM_APP)
        async for out in await llm_task.call_stream(call_data=request):
            yield out

    def do_action(self, prompt_response):
        return prompt_response

    def message_adjust(self):
        pass

    def has_history_messages(self) -> bool:
        """Whether there is a history messages

        Returns:
            bool: True if there is a history message, False otherwise
        """
        return len(self.history_messages) > 0

    def get_llm_speak(self, prompt_define_response):
        if hasattr(prompt_define_response, "thoughts"):
            if isinstance(prompt_define_response.thoughts, dict):
                if "speak" in prompt_define_response.thoughts:
                    speak_to_user = prompt_define_response.thoughts.get("speak")
                else:
                    speak_to_user = str(prompt_define_response.thoughts)
            else:
                if hasattr(prompt_define_response.thoughts, "speak"):
                    speak_to_user = prompt_define_response.thoughts.get("speak")
                elif hasattr(prompt_define_response.thoughts, "reasoning"):
                    speak_to_user = prompt_define_response.thoughts.get("reasoning")
                else:
                    speak_to_user = prompt_define_response.thoughts
        else:
            speak_to_user = prompt_define_response
        return speak_to_user

    async def _build_model_request(self) -> ModelRequest:
        input_values = await self.generate_input_values()
        # Load history
        self.history_messages = self.current_message.get_history_message()
        self.current_message.start_new_round()
        self.current_message.add_user_message(self.current_user_input)
        self.current_message.start_date = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.current_message.tokens = 0

        keep_start_rounds = (
            self.keep_start_rounds
            if self.prompt_template.need_historical_messages
            else 0
        )
        keep_end_rounds = (
            self.keep_end_rounds if self.prompt_template.need_historical_messages else 0
        )
        req_ctx = ModelRequestContext(
            stream=self.prompt_template.stream_out,
            user_name=self._chat_param.get("user_name"),
            sys_code=self._chat_param.get("sys_code"),
            chat_mode=self.chat_mode.value(),
            span_id=root_tracer.get_current_span_id(),
        )
        node = AppChatComposerOperator(
            model=self.llm_model,
            temperature=self._chat_param.get("temperature")
            or float(self.prompt_template.temperature),
            max_new_tokens=int(self.prompt_template.max_new_tokens),
            prompt=self.prompt_template.prompt,
            message_version=self._message_version,
            echo=self.llm_echo,
            streaming=self.prompt_template.stream_out,
            keep_start_rounds=keep_start_rounds,
            keep_end_rounds=keep_end_rounds,
            str_history=self.prompt_template.str_history,
            request_context=req_ctx,
        )
        node_input = ChatComposerInput(
            messages=self.history_messages, prompt_dict=input_values
        )
        # llm_messages = self.generate_llm_messages()
        model_request: ModelRequest = await node.call(call_data=node_input)
        model_request.context.cache_enable = self.model_cache_enable
        return model_request

    def stream_plugin_call(self, text):
        return text

    def stream_call_reinforce_fn(self, text):
        return text

    def _get_span_metadata(self, payload: Dict) -> Dict:
        metadata = {k: v for k, v in payload.items()}
        del metadata["prompt"]
        metadata["messages"] = list(
            map(lambda m: m if isinstance(m, dict) else m.dict(), metadata["messages"])
        )
        return metadata

    async def stream_call(self):
        # TODO Retry when server connection error
        payload = await self._build_model_request()

        logger.info(f"payload request: \n{payload}")
        ai_response_text = ""
        span = root_tracer.start_span(
            "BaseChat.stream_call", metadata=payload.to_dict()
        )
        payload.span_id = span.span_id
        try:
            msg = "<span style='color:red'>ERROR!</span> No response from model"
            view_msg = msg
            async for output in self.call_streaming_operator(payload):
                # Plugin research in result generation
                msg = self.prompt_template.output_parser.parse_model_stream_resp_ex(
                    output, 0
                )
                view_msg = self.stream_plugin_call(msg)
                view_msg = view_msg.replace("\n", "\\n")
                yield view_msg
            self.current_message.add_ai_message(msg)
            view_msg = self.stream_call_reinforce_fn(view_msg)
            self.current_message.add_view_message(view_msg)
            span.end()
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parse failed！" + str(e))
            self.current_message.add_view_message(
                f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
            )
            ### store current conversation
            span.end(metadata={"error": str(e)})
        await blocking_func_to_async(
            self._executor, self.current_message.end_current_round
        )

    async def nostream_call(self):
        payload = await self._build_model_request()
        span = root_tracer.start_span(
            "BaseChat.nostream_call", metadata=payload.to_dict()
        )
        logger.info(f"Request: \n{payload}")
        payload.span_id = span.span_id
        try:
            ai_response_text, view_message = await self._no_streaming_call_with_retry(
                payload
            )
            self.current_message.add_ai_message(ai_response_text)
            self.current_message.add_view_message(view_message)
            self.message_adjust()
            span.end()
        except BaseAppException as e:
            self.current_message.add_view_message(e.view)
            span.end(metadata={"error": str(e)})
        except Exception as e:
            view_message = f"<span style='color:red'>ERROR!</span> {str(e)}"
            self.current_message.add_view_message(view_message)
            span.end(metadata={"error": str(e)})

        # Store current conversation
        await blocking_func_to_async(
            self._executor, self.current_message.end_current_round
        )
        return self.current_ai_response()

    @async_retry(
        retries=CFG.DBGPT_APP_SCENE_NON_STREAMING_RETRIES_BASE,
        parallel_executions=CFG.DBGPT_APP_SCENE_NON_STREAMING_PARALLELISM_BASE,
        catch_exceptions=(Exception, BaseAppException),
    )
    async def _no_streaming_call_with_retry(self, payload):
        with root_tracer.start_span("BaseChat.invoke_worker_manager.generate"):
            model_output = await self.call_llm_operator(payload)

        ai_response_text = self.prompt_template.output_parser.parse_model_nostream_resp(
            model_output, self.prompt_template.sep
        )
        prompt_define_response = (
            self.prompt_template.output_parser.parse_prompt_response(ai_response_text)
        )
        metadata = {
            "model_output": model_output.to_dict(),
            "ai_response_text": ai_response_text,
            "prompt_define_response": self._parse_prompt_define_response(
                prompt_define_response
            ),
        }
        with root_tracer.start_span("BaseChat.do_action", metadata=metadata):
            result = await blocking_func_to_async(
                self._executor, self.do_action, prompt_define_response
            )

        speak_to_user = self.get_llm_speak(prompt_define_response)

        view_message = await blocking_func_to_async(
            self._executor,
            self.prompt_template.output_parser.parse_view_response,
            speak_to_user,
            result,
            prompt_define_response,
        )
        return ai_response_text, view_message.replace("\n", "\\n")

    async def get_llm_response(self):
        payload = await self._build_model_request()
        logger.info(f"Request: \n{payload}")
        ai_response_text = ""
        prompt_define_response = None
        try:
            model_output = await self.call_llm_operator(payload)
            ### output parse
            ai_response_text = (
                self.prompt_template.output_parser.parse_model_nostream_resp(
                    model_output, self.prompt_template.sep
                )
            )
            ### model result deal
            self.current_message.add_ai_message(ai_response_text)
            prompt_define_response = (
                self.prompt_template.output_parser.parse_prompt_response(
                    ai_response_text
                )
            )
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parse failed！" + str(e))
            self.current_message.add_view_message(
                f"""model response parse failed！{str(e)}\n  {ai_response_text} """
            )
        return prompt_define_response

    def _blocking_stream_call(self):
        logger.warn(
            "_blocking_stream_call is only temporarily used in webserver and will be deleted soon, please use stream_call to replace it for higher performance"
        )
        loop = get_or_create_event_loop()
        async_gen = self.stream_call()
        while True:
            try:
                value = loop.run_until_complete(async_gen.__anext__())
                yield value
            except StopAsyncIteration:
                break

    def _blocking_nostream_call(self):
        logger.warn(
            "_blocking_nostream_call is only temporarily used in webserver and will be deleted soon, please use nostream_call to replace it for higher performance"
        )
        loop = get_or_create_event_loop()
        try:
            return loop.run_until_complete(self.nostream_call())
        finally:
            loop.close()

    def call(self):
        if self.prompt_template.stream_out:
            yield self._blocking_stream_call()
        else:
            return self._blocking_nostream_call()

    async def prepare(self):
        pass

    def current_ai_response(self) -> str:
        for message in self.current_message.messages[-1:]:
            if message.type == "view":
                return message.content
        return None

    async def prompt_context_token_adapt(self, prompt) -> str:
        """prompt token adapt according to llm max context length"""
        model_metadata = await self.worker_manager.get_model_metadata(
            {"model": self.llm_model}
        )
        current_token_count = await self.worker_manager.count_token(
            {"model": self.llm_model, "prompt": prompt}
        )
        if current_token_count == -1:
            logger.warning(
                "tiktoken not installed, please `pip install tiktoken` first"
            )
        template_define_token_count = 0
        if len(self.prompt_template.template_define) > 0:
            template_define_token_count = await self.worker_manager.count_token(
                {
                    "model": self.llm_model,
                    "prompt": self.prompt_template.template_define,
                }
            )
            current_token_count += template_define_token_count
        if (
            current_token_count + self.prompt_template.max_new_tokens
        ) > model_metadata.context_length:
            prompt = prompt[
                : (
                    model_metadata.context_length
                    - self.prompt_template.max_new_tokens
                    - template_define_token_count
                )
            ]
        return prompt

    def generate(self, p) -> str:
        """
        generate context for LLM input
        Args:
            p:

        Returns:

        """
        pass

    def _parse_prompt_define_response(self, prompt_define_response: Any) -> Any:
        if not prompt_define_response:
            return ""
        if isinstance(prompt_define_response, str) or isinstance(
            prompt_define_response, dict
        ):
            return prompt_define_response
        if isinstance(prompt_define_response, tuple):
            if hasattr(prompt_define_response, "_asdict"):
                # namedtuple
                return prompt_define_response._asdict()
            else:
                return dict(
                    zip(range(len(prompt_define_response)), prompt_define_response)
                )
        else:
            return prompt_define_response

    def _generate_numbered_list(self) -> str:
        """this function is moved from excel_analyze/chat.py,and used by subclass.
        Returns:

        """
        antv_charts = [
            {"response_line_chart": "used to display comparative trend analysis data"},
            {
                "response_pie_chart": "suitable for scenarios such as proportion and distribution statistics"
            },
            {
                "response_table": "suitable for display with many display columns or non-numeric columns"
            },
            # {"response_data_text":" the default display method, suitable for single-line or simple content display"},
            {
                "response_scatter_plot": "Suitable for exploring relationships between variables, detecting outliers, etc."
            },
            {
                "response_bubble_chart": "Suitable for relationships between multiple variables, highlighting outliers or special situations, etc."
            },
            {
                "response_donut_chart": "Suitable for hierarchical structure representation, category proportion display and highlighting key categories, etc."
            },
            {
                "response_area_chart": "Suitable for visualization of time series data, comparison of multiple groups of data, analysis of data change trends, etc."
            },
            {
                "response_heatmap": "Suitable for visual analysis of time series data, large-scale data sets, distribution of classified data, etc."
            },
        ]

        return "\n".join(
            f"{key}:{value}"
            for dict_item in antv_charts
            for key, value in dict_item.items()
        )
