import datetime
import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional, Type, TypeVar, Union

from dbgpt._private.config import Config
from dbgpt.component import ComponentType, SystemApp
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    LLMClient,
    MessagesPlaceholder,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
    SystemPromptTemplate,
)
from dbgpt.core.interface.file import FileStorageClient
from dbgpt.core.interface.media import MediaContent
from dbgpt.core.interface.message import (
    HumanMessage,
    ModelMessage,
    StorageConversation,
)
from dbgpt.core.schema.types import (
    ChatCompletionUserMessageParam,
)
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.util import get_or_create_event_loop
from dbgpt.util.annotations import Deprecated
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.retry import async_retry
from dbgpt.util.tracer import root_tracer, trace
from dbgpt_app.scene.base import AppScenePromptTemplateAdapter, ChatScene
from dbgpt_app.scene.operators.app_operator import (
    AppChatComposerOperator,
    ChatComposerInput,
    build_cached_chat_operator,
)
from dbgpt_serve.conversation.serve import Serve as ConversationServe
from dbgpt_serve.core.config import BufferWindowGPTsAppMemoryConfig, GPTsAppCommonConfig
from dbgpt_serve.file.serve import Serve as FileServe
from dbgpt_serve.prompt.service.service import Service as PromptService

from .exceptions import BaseAppException, ContextAppException

logger = logging.getLogger(__name__)
CFG = Config()

C = TypeVar("C", bound="GPTsAppCommonConfig")


@dataclass
class ChatParam:
    chat_session_id: str
    current_user_input: Union[str, ChatCompletionUserMessageParam]
    model_name: str
    select_param: Any
    chat_mode: ChatScene
    user_name: str = ""
    sys_code: str = ""
    app_code: str = ""
    temperature: Optional[float] = field(default=None)
    max_new_tokens: Optional[int] = field(default=None)
    message_version: str = "v2"
    model_cache_enable: bool = False
    prompt_code: Optional[str] = None
    ext_info: Optional[Dict[str, Any]] = None
    app_config: Optional[GPTsAppCommonConfig] = None

    def real_app_config(self, type_class: Type[C]) -> C:
        if self.app_config is None:
            return type_class()
        if not isinstance(self.app_config, type_class):
            return type_class(**self.app_config.to_dict())
        return self.app_config

    def real_user_input(self) -> HumanMessage:
        return HumanMessage.parse_chat_completion_message(
            self.current_user_input, ignore_unknown_media=True
        )


def _build_conversation(
    chat_mode: ChatScene,
    chat_param: ChatParam,
    model_name: str,
    conv_serve: ConversationServe,
) -> StorageConversation:
    param_type = ""
    param_value = ""
    if chat_param.select_param:
        if len(chat_mode.param_types()) > 0:
            param_type = chat_mode.param_types()[0]
        param_value = chat_param.select_param
    return StorageConversation(
        chat_param.chat_session_id,
        chat_mode=chat_mode.value(),
        user_name=chat_param.user_name,
        sys_code=chat_param.sys_code,
        app_code=chat_param.app_code,
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
    # Some model not support system role, this config is used to control whether to
    # convert system message to human message
    auto_convert_message: bool = True

    @classmethod
    @abstractmethod
    def param_class(cls) -> Type[GPTsAppCommonConfig]:
        """Return the parameter class of the chat"""

    @trace("BaseChat.__init__")
    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """Chat Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) select param
        """
        self.system_app = system_app
        self.app_config = self.system_app.config.configs.get("app_config")
        self.web_config = self.app_config.service.web
        self.model_config = self.app_config.models
        self.chat_session_id = chat_param.chat_session_id
        self.chat_mode = chat_param.chat_mode
        self.current_user_input: HumanMessage = chat_param.real_user_input()
        self.llm_model = (
            chat_param.model_name
            if chat_param.model_name
            else self.model_config.default_llm
        )
        self.llm_echo = False
        self.worker_manager = self.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        self.model_cache_enable = chat_param.model_cache_enable
        self.prompt_code = chat_param.prompt_code

        self.prompt_template: AppScenePromptTemplateAdapter = (
            CFG.prompt_template_registry.get_prompt_template(
                self.chat_mode.value(),
                language=self.system_app.config.configs.get(
                    "dbgpt.app.global.language"
                ),
                model_name=self.llm_model,
            )
        )
        self._prompt_service = PromptService.get_instance(self.system_app)
        if self.prompt_code:
            # adapt prompt template according to the prompt code
            prompt_template = self._prompt_service.get_template(self.prompt_code)
            chat_prompt_template = ChatPromptTemplate(
                messages=[
                    SystemPromptTemplate.from_template(prompt_template.template),
                    MessagesPlaceholder(variable_name="chat_history"),
                    HumanPromptTemplate.from_template("{question}"),
                ]
            )
            self.prompt_template = AppScenePromptTemplateAdapter(
                prompt=chat_prompt_template,
                template_scene=self.prompt_template.template_scene,
                stream_out=self.prompt_template.stream_out,
                output_parser=self.prompt_template.output_parser,
            )
        self._conv_serve = ConversationServe.get_instance(self.system_app)
        self._file_serve = FileServe.get_instance(self.system_app)
        self.current_message: StorageConversation = _build_conversation(
            self.chat_mode, chat_param, self.llm_model, self._conv_serve
        )
        self.history_messages = self.current_message.get_history_message()
        self.current_tokens_used: int = 0
        # The executor to submit blocking function
        self._executor = self.system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

        # In v1, we will transform the message to compatible format of specific model
        # In the future, we will upgrade the message version to v2, and the message
        # will be compatible with all models
        self._message_version = chat_param.message_version
        self._chat_param = chat_param
        self.fs_client = FileStorageClient.get_instance(system_app)

    async def generate_input_values(self) -> Dict:
        """Generate input to LLM

        Please note that you must not perform any blocking operations in this function

        Returns:
            a dictionary to be formatted by prompt template
        """
        return self.parse_user_input()

    @property
    def llm_client(self) -> LLMClient:
        """Return the LLM client."""
        worker_manager = self.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return DefaultLLMClient(
            worker_manager, auto_convert_message=self.auto_convert_message
        )

    async def call_llm_operator(self, request: ModelRequest) -> ModelOutput:
        llm_task = build_cached_chat_operator(self.llm_client, False, self.system_app)
        return await llm_task.call(call_data=request)

    async def call_streaming_operator(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelOutput]:
        llm_task = build_cached_chat_operator(self.llm_client, True, self.system_app)
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

    def llm_max_new_tokens(self):
        """Get the max new tokens for LLM generation.

        The order of priority is:
        1. chat_param.max_new_tokens(From API)
        2. app_config.max_new_tokens(From config file)
        3. prompt_template.max_new_tokens(From prompt template)
        """
        if self._chat_param.max_new_tokens:
            return int(self._chat_param.max_new_tokens)
        elif self._chat_param.app_config and self._chat_param.app_config.max_new_tokens:
            return int(self.app_config.max_new_tokens)
        return self.prompt_template.max_new_tokens

    def llm_temperature(self):
        """Get the temperature for LLM generation.

        The order of priority is:
        1. chat_param.temperature(From API)
        2. app_config.temperature(From config file)
        3. prompt_template.temperature(From prompt template)
        """
        if self._chat_param.temperature is not None:
            return float(self._chat_param.temperature)
        elif (
            self._chat_param.app_config
            and self._chat_param.app_config.temperature is not None
        ):
            return float(self.app_config.temperature)
        return self.prompt_template.temperature

    def memory_config(self):
        if self._chat_param.app_config and self._chat_param.app_config.memory:
            return self._chat_param.app_config.memory
        return BufferWindowGPTsAppMemoryConfig()

    def parse_user_input(self) -> Dict[str, Any]:
        """Parse user input to a dictionary.

        Returns:
            Dict[str, Any]: parsed user input
        """
        user_params = {"input": self.current_user_input.last_text}
        if self.current_user_input.has_media:
            user_params["media_input"] = [self.current_user_input]
        return user_params

    async def _build_model_request(self) -> ModelRequest:
        input_values = await self.generate_input_values()
        # Load history
        self.history_messages = self.current_message.get_history_message()
        self.current_message.start_new_round()
        self.current_message.add_user_message(self.current_user_input.content)
        self.current_message.start_date = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.current_message.tokens = 0

        req_ctx = ModelRequestContext(
            stream=self.prompt_template.stream_out,
            user_name=self._chat_param.user_name,
            sys_code=self._chat_param.sys_code,
            chat_mode=self.chat_mode.value(),
            span_id=root_tracer.get_current_span_id(),
        )
        node = AppChatComposerOperator(
            model=self.llm_model,
            temperature=self.llm_temperature(),
            max_new_tokens=self.llm_max_new_tokens(),
            prompt=self.prompt_template.prompt,
            llm_client=self.llm_client,
            memory=self.memory_config(),
            message_version=self._message_version,
            echo=self.llm_echo,
            streaming=self.prompt_template.stream_out,
            str_history=self.prompt_template.str_history,
            request_context=req_ctx,
        )
        node_input = ChatComposerInput(
            messages=self.history_messages, prompt_dict=input_values
        )
        model_request: ModelRequest = await node.call(call_data=node_input)
        model_request.context.cache_enable = self.model_cache_enable
        if model_request.messages:
            for msg in model_request.messages:
                if isinstance(msg, ModelMessage) and isinstance(msg.content, list):
                    msg.content = MediaContent.replace_url(
                        msg.content, self._file_serve.replace_uri
                    )
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

    async def stream_call(
        self, text_output: bool = True, incremental: bool = False
    ) -> AsyncIterator[Union[ModelOutput, str]]:
        # TODO Retry when server connection error
        payload = await self._build_model_request()

        logger.info(f"payload request: \n{payload}")
        ai_response_text = ""
        span = root_tracer.start_span(
            "BaseChat.stream_call", metadata=payload.to_dict()
        )
        payload.span_id = span.span_id
        full_text = ""
        full_thinking_text = ""
        previous_text = ""
        previous_thinking_text = ""
        try:
            final_output: Optional[ModelOutput] = None
            async for output in self.call_streaming_operator(payload):
                # Plugin research in result generation
                final_output = output
                model_output = (
                    self.prompt_template.output_parser.parse_model_stream_resp_ex(
                        output,
                        text_output=False,
                    )
                )
                text_msg = model_output.text if model_output.has_text else ""
                view_msg = self.stream_plugin_call(text_msg)
                view_msg = model_output.gen_text_with_thinking(new_text=view_msg)
                view_msg = view_msg.replace("\n", "\\n")

                if text_output:
                    full_text = view_msg
                    # Return the incremental text
                    delta_text = full_text[len(previous_text) :]
                    previous_text = (
                        full_text
                        if len(full_text) > len(previous_text)
                        else previous_text
                    )
                    yield delta_text if incremental else full_text
                else:
                    if model_output.has_thinking:
                        full_thinking_text = model_output.thinking_text
                    if model_output.has_text:
                        full_text = model_output.text
                    if not incremental:
                        yield ModelOutput.build(
                            full_text,
                            full_thinking_text,
                            error_code=model_output.error_code,
                            usage=model_output.usage,
                            finish_reason=model_output.finish_reason,
                            metrics=model_output.metrics,
                        )
                    else:
                        # Return the incremental text
                        delta_text = full_text[len(previous_text) :]
                        previous_text = (
                            full_text
                            if len(full_text) > len(previous_text)
                            else previous_text
                        )
                        delta_thinking_text = full_thinking_text[
                            len(previous_thinking_text) :
                        ]
                        previous_thinking_text = (
                            full_thinking_text
                            if len(full_thinking_text) > len(previous_thinking_text)
                            else previous_thinking_text
                        )
                        yield ModelOutput.build(
                            delta_text,
                            delta_thinking_text,
                            error_code=model_output.error_code,
                            usage=model_output.usage,
                            finish_reason=model_output.finish_reason,
                            metrics=model_output.metrics,
                        )
            ai_response_text, view_message = await self._handle_final_output(
                final_output, incremental=incremental
            )
            full_text = view_message if text_output else final_output.text
            # Return the incremental text
            delta_text = full_text[len(previous_text) :]
            result_text = delta_text if incremental else full_text
            if text_output:
                yield result_text
            else:
                yield ModelOutput.build(
                    result_text,
                    "",
                    error_code=final_output.error_code,
                    usage=final_output.usage,
                    finish_reason=final_output.finish_reason,
                    metrics=final_output.metrics,
                )

            self.current_message.add_ai_message(ai_response_text)
            view_msg = self.stream_call_reinforce_fn(view_message)
            self.current_message.add_view_message(view_msg)
            span.end()
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parse failed！" + str(e))
            if not text_output:
                yield ModelOutput.build(
                    f"{str(e)}",
                    "",
                    error_code=-1,
                )
            else:
                err_view_meg = (
                    f'<span style="color:red">ERROR!</span>{str(e)}\n{ai_response_text}'
                )
                yield err_view_meg
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
            self.current_message.add_view_message(e.get_ui_error())
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
        return await self._handle_final_output(model_output)

    async def _handle_final_output(
        self, final_output: ModelOutput, incremental: bool = False
    ):
        model_output = final_output
        parsed_output = self.prompt_template.output_parser.parse_model_nostream_resp(
            model_output, text_output=False
        )
        ai_response_text = parsed_output.text if parsed_output.has_text else ""
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
        try:
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
            if parsed_output.has_thinking and not incremental:
                view_message = parsed_output.gen_text_with_thinking(
                    new_text=view_message
                )
            return ai_response_text, view_message.replace("\n", "\\n")
        except BaseAppException as e:
            raise ContextAppException(e.message, e.view, model_output) from e

        except Exception as e:
            logger.error("model response parse failed！" + str(e))
            raise ContextAppException(
                f"model response parse failed！{str(e)}\n  {ai_response_text}",
                f"<span style='color:red'>ERROR!</span> {str(e)}",
                model_output,
            )

    @Deprecated(version="0.7.0", remove_version="0.8.0")
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
                    model_output
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
        logger.warning(
            "_blocking_stream_call is only temporarily used in webserver and will be "
            "deleted soon, please use stream_call to replace it for higher performance"
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
        logger.warning(
            "_blocking_nostream_call is only temporarily used in webserver and will "
            "be deleted soon, please use nostream_call to replace it for higher "
            "performance"
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
                "response_pie_chart": "suitable for scenarios such as proportion and "
                "distribution statistics"
            },
            {
                "response_table": "suitable for display with many display columns or "
                "non-numeric columns"
            },
            # {"response_data_text":" the default display method, suitable for
            # single-line or simple content display"},
            {
                "response_scatter_chart": "Suitable for exploring relationships between"
                " variables, detecting outliers, etc."
            },
            {
                "response_bubble_chart": "Suitable for relationships between multiple"
                " variables, highlighting outliers or special situations, etc."
            },
            {
                "response_donut_chart": "Suitable for hierarchical structure "
                "representation, category proportion display and highlighting key "
                "categories, etc."
            },
            {
                "response_area_chart": "Suitable for visualization of time series data,"
                " comparison of multiple groups of data, analysis of data change "
                "trends, etc."
            },
            {
                "response_heatmap": "Suitable for visual analysis of time series data,"
                " large-scale data sets, distribution of classified data, etc."
            },
            {
                "response_vector_chart": "Suitable for projecting high-dimensional "
                "vector data onto a two-dimensional plot through the PCA algorithm."
            },
        ]

        return "\n".join(
            f"{key}:{value}"
            for dict_item in antv_charts
            for key, value in dict_item.items()
        )
