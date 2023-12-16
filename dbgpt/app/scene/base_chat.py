import datetime
import traceback
import warnings
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, List, Dict

from dbgpt._private.config import Config
from dbgpt.component import ComponentType
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.core.interface.message import OnceConversation
from dbgpt.util import get_or_create_event_loop
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace
from dbgpt._private.pydantic import Extra
from dbgpt.storage.chat_history.chat_hisotry_factory import ChatHistory
from dbgpt.core.awel import BaseOperator, SimpleCallDataInputSource, InputOperator, DAG
from dbgpt.model.operator.model_operator import ModelOperator, ModelStreamOperator

logger = logging.getLogger(__name__)
headers = {"User-Agent": "dbgpt Client"}
CFG = Config()


class BaseChat(ABC):
    """DB-GPT Chat Service Base Module
    Include:
    stream_call():scene + prompt -> stream response
    nostream_call():scene + prompt -> nostream response
    """

    chat_scene: str = None
    llm_model: Any = None
    # By default, keep the last two rounds of conversation records as the context
    chat_retention_rounds: int = 0

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

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
        self.model_cache_enable = chat_param.get("model_cache_enable", False)

        ### load prompt template
        # self.prompt_template: PromptTemplate = CFG.prompt_templates[
        #     self.chat_mode.value()
        # ]
        self.prompt_template: PromptTemplate = (
            CFG.prompt_template_registry.get_prompt_template(
                self.chat_mode.value(),
                language=CFG.LANGUAGE,
                model_name=self.llm_model,
                proxyllm_backend=CFG.PROXYLLM_BACKEND,
            )
        )
        chat_history_fac = ChatHistory()
        ### can configurable storage methods
        self.memory = chat_history_fac.get_store_instance(chat_param["chat_session_id"])

        self.history_message: List[OnceConversation] = self.memory.messages()
        self.current_message: OnceConversation = OnceConversation(
            self.chat_mode.value(),
            user_name=chat_param.get("user_name"),
            sys_code=chat_param.get("sys_code"),
        )
        self.current_message.model_name = self.llm_model
        if chat_param["select_param"]:
            if len(self.chat_mode.param_types()) > 0:
                self.current_message.param_type = self.chat_mode.param_types()[0]
            self.current_message.param_value = chat_param["select_param"]
        self.current_tokens_used: int = 0
        # The executor to submit blocking function
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

        self._model_operator: BaseOperator = _build_model_operator()
        self._model_stream_operator: BaseOperator = _build_model_operator(
            is_stream=True, dag_name="llm_stream_model_dag"
        )

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

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

    def do_action(self, prompt_response):
        return prompt_response

    def message_adjust(self):
        pass

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

    async def __call_base(self):
        input_values = await self.generate_input_values()
        ### Chat sequence advance
        self.current_message.chat_order = len(self.history_message) + 1
        self.current_message.add_user_message(
            self.current_user_input, check_duplicate_type=True
        )
        self.current_message.start_date = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.current_message.tokens = 0
        if self.prompt_template.template:
            metadata = {
                "template_scene": self.prompt_template.template_scene,
                "input_values": input_values,
            }
            with root_tracer.start_span(
                "BaseChat.__call_base.prompt_template.format", metadata=metadata
            ):
                current_prompt = self.prompt_template.format(**input_values)
            self.current_message.add_system_message(current_prompt)

        llm_messages = self.generate_llm_messages()
        if not CFG.NEW_SERVER_MODE:
            # Not new server mode, we convert the message format(List[ModelMessage]) to list of dict
            # fix the error of "Object of type ModelMessage is not JSON serializable" when passing the payload to request.post
            llm_messages = list(map(lambda m: m.dict(), llm_messages))
        payload = {
            "model": self.llm_model,
            "prompt": self.generate_llm_text(),
            "messages": llm_messages,
            "temperature": float(self.prompt_template.temperature),
            "max_new_tokens": int(self.prompt_template.max_new_tokens),
            "echo": self.llm_echo,
        }
        return payload

    def stream_plugin_call(self, text):
        return text

    def stream_call_reinforce_fn(self, text):
        return text

    async def check_iterator_end(iterator):
        try:
            await asyncio.anext(iterator)
            return False  # 迭代器还有下一个元素
        except StopAsyncIteration:
            return True  # 迭代器已经执行结束

    def _get_span_metadata(self, payload: Dict) -> Dict:
        metadata = {k: v for k, v in payload.items()}
        del metadata["prompt"]
        metadata["messages"] = list(
            map(lambda m: m if isinstance(m, dict) else m.dict(), metadata["messages"])
        )
        return metadata

    async def stream_call(self):
        # TODO Retry when server connection error
        payload = await self.__call_base()

        self.skip_echo_len = len(payload.get("prompt").replace("</s>", " ")) + 11
        logger.info(f"payload request: \n{payload}")
        ai_response_text = ""
        span = root_tracer.start_span(
            "BaseChat.stream_call", metadata=self._get_span_metadata(payload)
        )
        payload["span_id"] = span.span_id
        payload["model_cache_enable"] = self.model_cache_enable
        try:
            async for output in await self._model_stream_operator.call_stream(
                call_data={"data": payload}
            ):
                # Plugin research in result generation
                msg = self.prompt_template.output_parser.parse_model_stream_resp_ex(
                    output, self.skip_echo_len
                )
                view_msg = self.stream_plugin_call(msg)
                view_msg = view_msg.replace("\n", "\\n")
                yield view_msg
            self.current_message.add_ai_message(msg, update_if_exist=True)
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
        self.memory.append(self.current_message)

    async def nostream_call(self):
        payload = await self.__call_base()
        logger.info(f"Request: \n{payload}")
        ai_response_text = ""
        span = root_tracer.start_span(
            "BaseChat.nostream_call", metadata=self._get_span_metadata(payload)
        )
        payload["span_id"] = span.span_id
        payload["model_cache_enable"] = self.model_cache_enable
        try:
            with root_tracer.start_span("BaseChat.invoke_worker_manager.generate"):
                model_output = await self._model_operator.call(
                    call_data={"data": payload}
                )

            ### output parse
            ai_response_text = (
                self.prompt_template.output_parser.parse_model_nostream_resp(
                    model_output, self.prompt_template.sep
                )
            )
            ### model result deal
            self.current_message.add_ai_message(ai_response_text, update_if_exist=True)
            prompt_define_response = (
                self.prompt_template.output_parser.parse_prompt_response(
                    ai_response_text
                )
            )
            metadata = {
                "model_output": model_output.to_dict(),
                "ai_response_text": ai_response_text,
                "prompt_define_response": self._parse_prompt_define_response(
                    prompt_define_response
                ),
            }
            with root_tracer.start_span("BaseChat.do_action", metadata=metadata):
                ###  run
                result = await blocking_func_to_async(
                    self._executor, self.do_action, prompt_define_response
                )

            ### llm speaker
            speak_to_user = self.get_llm_speak(prompt_define_response)

            # view_message = self.prompt_template.output_parser.parse_view_response(
            #     speak_to_user, result
            # )
            view_message = await blocking_func_to_async(
                self._executor,
                self.prompt_template.output_parser.parse_view_response,
                speak_to_user,
                result,
                prompt_define_response,
            )

            view_message = view_message.replace("\n", "\\n")
            self.current_message.add_view_message(view_message)
            self.message_adjust()

            span.end()
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parase faild！" + str(e))
            self.current_message.add_view_message(
                f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
            )
            span.end(metadata={"error": str(e)})
        ### store dialogue
        self.memory.append(self.current_message)
        return self.current_ai_response()

    async def get_llm_response(self):
        payload = await self.__call_base()
        logger.info(f"Request: \n{payload}")
        ai_response_text = ""
        payload["model_cache_enable"] = self.model_cache_enable
        try:
            model_output = await self._model_operator.call(call_data={"data": payload})
            ### output parse
            ai_response_text = (
                self.prompt_template.output_parser.parse_model_nostream_resp(
                    model_output, self.prompt_template.sep
                )
            )
            ### model result deal
            self.current_message.add_ai_message(ai_response_text, update_if_exist=True)
            prompt_define_response = None
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

    def generate_llm_text(self) -> str:
        warnings.warn("This method is deprecated - please use `generate_llm_messages`.")
        text = ""
        ### Load scene setting or character definition
        if self.prompt_template.template_define:
            text += self.prompt_template.template_define + self.prompt_template.sep
        ### Load prompt
        text += _load_system_message(self.current_message, self.prompt_template)

        ### Load examples
        text += _load_example_messages(self.prompt_template)

        ### Load History
        text += _load_history_messages(
            self.prompt_template, self.history_message, self.chat_retention_rounds
        )

        ### Load User Input
        text += _load_user_message(self.current_message, self.prompt_template)
        return text

    def generate_llm_messages(self) -> List[ModelMessage]:
        """
        Structured prompt messages interaction between dbgpt-server and llm-server
        See https://github.com/csunny/DB-GPT/issues/328
        """
        messages = []
        ### Load scene setting or character definition as system message
        if self.prompt_template.template_define:
            messages.append(
                ModelMessage(
                    role=ModelMessageRoleType.SYSTEM,
                    content=self.prompt_template.template_define,
                )
            )
        ### Load prompt
        messages += _load_system_message(
            self.current_message, self.prompt_template, str_message=False
        )
        ### Load examples
        messages += _load_example_messages(self.prompt_template, str_message=False)

        ### Load History
        messages += _load_history_messages(
            self.prompt_template,
            self.history_message,
            self.chat_retention_rounds,
            str_message=False,
        )

        ### Load User Input
        messages += _load_user_message(
            self.current_message, self.prompt_template, str_message=False
        )
        return messages

    def current_ai_response(self) -> str:
        for message in self.current_message.messages:
            if message.type == "view":
                return message.content
        return None

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

        # command_strings = []
        # if CFG.command_disply:
        #     for name, item in CFG.command_disply.commands.items():
        #         if item.enabled:
        #             command_strings.append(f"{name}:{item.description}")
        # command_strings += [
        #     str(item)
        #     for item in CFG.command_disply.commands.values()
        #     if item.enabled
        # ]
        return "\n".join(
            f"{key}:{value}"
            for dict_item in antv_charts
            for key, value in dict_item.items()
        )


def _build_model_operator(
    is_stream: bool = False, dag_name: str = "llm_model_dag"
) -> BaseOperator:
    """Builds and returns a model processing workflow (DAG) operator.

    This function constructs a Directed Acyclic Graph (DAG) for processing data using a model.
    It includes caching and branching logic to either fetch results from a cache or process
    data using the model. It supports both streaming and non-streaming modes.

    .. code-block:: python
        input_node >> cache_check_branch_node
        cache_check_branch_node >> model_node >> save_cached_node >> join_node
        cache_check_branch_node >> cached_node >> join_node

    equivalent to::

                          -> model_node -> save_cached_node ->
                         /                                    \
        input_node -> cache_check_branch_node                   ---> join_node
                        \                                     /
                         -> cached_node ------------------- ->

    Args:
        is_stream (bool): Flag to determine if the operator should process data in streaming mode.
        dag_name (str): Name of the DAG.

    Returns:
        BaseOperator: The final operator in the constructed DAG, typically a join node.
    """
    from dbgpt.model.cluster import WorkerManagerFactory
    from dbgpt.core.awel import JoinOperator
    from dbgpt.model.operator.model_operator import (
        ModelCacheBranchOperator,
        CachedModelStreamOperator,
        CachedModelOperator,
        ModelSaveCacheOperator,
        ModelStreamSaveCacheOperator,
    )
    from dbgpt.storage.cache import CacheManager

    # Fetch worker and cache managers from the system configuration
    worker_manager = CFG.SYSTEM_APP.get_component(
        ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
    ).create()
    cache_manager: CacheManager = CFG.SYSTEM_APP.get_component(
        ComponentType.MODEL_CACHE_MANAGER, CacheManager
    )
    # Define task names for the model and cache nodes
    model_task_name = "llm_model_node"
    cache_task_name = "llm_model_cache_node"

    with DAG(dag_name):
        # Create an input node
        input_node = InputOperator(SimpleCallDataInputSource())
        # Determine if the workflow should operate in streaming mode
        if is_stream:
            model_node = ModelStreamOperator(worker_manager, task_name=model_task_name)
            cached_node = CachedModelStreamOperator(
                cache_manager, task_name=cache_task_name
            )
            save_cached_node = ModelStreamSaveCacheOperator(cache_manager)
        else:
            model_node = ModelOperator(worker_manager, task_name=model_task_name)
            cached_node = CachedModelOperator(cache_manager, task_name=cache_task_name)
            save_cached_node = ModelSaveCacheOperator(cache_manager)

        # Create a branch node to decide between fetching from cache or processing with the model
        cache_check_branch_node = ModelCacheBranchOperator(
            cache_manager,
            model_task_name="llm_model_node",
            cache_task_name="llm_model_cache_node",
        )
        # Create a join node to merge outputs from the model and cache nodes, just keep the first not empty output
        join_node = JoinOperator(
            combine_function=lambda model_out, cache_out: cache_out or model_out
        )

        # Define the workflow structure using the >> operator
        input_node >> cache_check_branch_node
        cache_check_branch_node >> model_node >> save_cached_node >> join_node
        cache_check_branch_node >> cached_node >> join_node

    return join_node


def _load_system_message(
    current_message: OnceConversation,
    prompt_template: PromptTemplate,
    str_message: bool = True,
):
    system_convs = current_message.get_system_messages()
    system_text = ""
    system_messages = []
    for system_conv in system_convs:
        system_text += (
            system_conv.type + ":" + system_conv.content + prompt_template.sep
        )
        system_messages.append(
            ModelMessage(role=system_conv.type, content=system_conv.content)
        )
    return system_text if str_message else system_messages


def _load_user_message(
    current_message: OnceConversation,
    prompt_template: PromptTemplate,
    str_message: bool = True,
):
    user_conv = current_message.get_latest_user_message()
    user_messages = []
    if user_conv:
        user_text = user_conv.type + ":" + user_conv.content + prompt_template.sep
        user_messages.append(
            ModelMessage(role=user_conv.type, content=user_conv.content)
        )
        return user_text if str_message else user_messages
    else:
        raise ValueError("Hi! What do you want to talk about？")


def _load_example_messages(prompt_template: PromptTemplate, str_message: bool = True):
    example_text = ""
    example_messages = []
    if prompt_template.example_selector:
        for round_conv in prompt_template.example_selector.examples():
            for round_message in round_conv["messages"]:
                if not round_message["type"] in [
                    ModelMessageRoleType.VIEW,
                    ModelMessageRoleType.SYSTEM,
                ]:
                    message_type = round_message["type"]
                    message_content = round_message["data"]["content"]
                    example_text += (
                        message_type + ":" + message_content + prompt_template.sep
                    )
                    example_messages.append(
                        ModelMessage(role=message_type, content=message_content)
                    )
    return example_text if str_message else example_messages


def _load_history_messages(
    prompt_template: PromptTemplate,
    history_message: List[OnceConversation],
    chat_retention_rounds: int,
    str_message: bool = True,
):
    history_text = ""
    history_messages = []
    if prompt_template.need_historical_messages:
        if history_message:
            logger.info(
                f"There are already {len(history_message)} rounds of conversations! Will use {chat_retention_rounds} rounds of content as history!"
            )
        if len(history_message) > chat_retention_rounds:
            for first_message in history_message[0]["messages"]:
                if not first_message["type"] in [
                    ModelMessageRoleType.VIEW,
                    ModelMessageRoleType.SYSTEM,
                ]:
                    message_type = first_message["type"]
                    message_content = first_message["data"]["content"]
                    history_text += (
                        message_type + ":" + message_content + prompt_template.sep
                    )
                    history_messages.append(
                        ModelMessage(role=message_type, content=message_content)
                    )
            if chat_retention_rounds > 1:
                index = chat_retention_rounds - 1
                for round_conv in history_message[-index:]:
                    for round_message in round_conv["messages"]:
                        if not round_message["type"] in [
                            ModelMessageRoleType.VIEW,
                            ModelMessageRoleType.SYSTEM,
                        ]:
                            message_type = round_message["type"]
                            message_content = round_message["data"]["content"]
                            history_text += (
                                message_type
                                + ":"
                                + message_content
                                + prompt_template.sep
                            )
                            history_messages.append(
                                ModelMessage(role=message_type, content=message_content)
                            )

        else:
            ### user all history
            for conversation in history_message:
                for message in conversation["messages"]:
                    ### histroy message not have promot and view info
                    if not message["type"] in [
                        ModelMessageRoleType.VIEW,
                        ModelMessageRoleType.SYSTEM,
                    ]:
                        message_type = message["type"]
                        message_content = message["data"]["content"]
                        history_text += (
                            message_type + ":" + message_content + prompt_template.sep
                        )
                        history_messages.append(
                            ModelMessage(role=message_type, content=message_content)
                        )

    return history_text if str_message else history_messages
