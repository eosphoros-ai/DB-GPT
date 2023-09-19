import datetime
import traceback
import warnings
from abc import ABC, abstractmethod
from typing import Any, List, Dict

from pilot.configs.config import Config
from pilot.configs.model_config import LOGDIR
from pilot.component import ComponentType
from pilot.memory.chat_history.base import BaseChatHistoryMemory
from pilot.memory.chat_history.duckdb_history import DuckdbHistoryMemory
from pilot.memory.chat_history.file_history import FileHistoryMemory
from pilot.memory.chat_history.mem_history import MemHistoryMemory
from pilot.prompts.prompt_new import PromptTemplate
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType
from pilot.scene.message import OnceConversation
from pilot.utils import build_logger, get_or_create_event_loop
from pydantic import Extra

logger = build_logger("BaseChat", LOGDIR + "BaseChat.log")
headers = {"User-Agent": "dbgpt Client"}
CFG = Config()


class BaseChat(ABC):
    chat_scene: str = None
    llm_model: Any = None
    # By default, keep the last two rounds of conversation records as the context
    chat_retention_rounds: int = 0

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    def __init__(self, chat_param: Dict):
        self.chat_session_id = chat_param["chat_session_id"]
        self.chat_mode = chat_param["chat_mode"]
        self.current_user_input: str = chat_param["current_user_input"]
        self.llm_model = (
            chat_param["model_name"] if chat_param["model_name"] else CFG.LLM_MODEL
        )
        self.llm_echo = False

        ### load prompt template
        # self.prompt_template: PromptTemplate = CFG.prompt_templates[
        #     self.chat_mode.value()
        # ]
        self.prompt_template: PromptTemplate = (
            CFG.prompt_template_registry.get_prompt_template(
                self.chat_mode.value(),
                language=CFG.LANGUAGE,
                model_name=CFG.LLM_MODEL,
                proxyllm_backend=CFG.PROXYLLM_BACKEND,
            )
        )

        ### can configurable storage methods
        self.memory = DuckdbHistoryMemory(chat_param["chat_session_id"])

        self.history_message: List[OnceConversation] = self.memory.messages()
        self.current_message: OnceConversation = OnceConversation(
            self.chat_mode.value()
        )
        self.current_message.model_name = self.llm_model
        if chat_param["select_param"]:
            if len(self.chat_mode.param_types()) > 0:
                self.current_message.param_type = self.chat_mode.param_types()[0]
            self.current_message.param_value = chat_param["select_param"]
        self.current_tokens_used: int = 0

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def chat_type(self) -> str:
        raise NotImplementedError("Not supported for this chat type.")

    @abstractmethod
    def generate_input_values(self):
        pass

    def do_action(self, prompt_response):
        return prompt_response

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

    def __call_base(self):
        input_values = self.generate_input_values()
        ### Chat sequence advance
        self.current_message.chat_order = len(self.history_message) + 1
        self.current_message.add_user_message(self.current_user_input)
        self.current_message.start_date = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.current_message.tokens = 0
        if self.prompt_template.template:
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
            "stop": self.prompt_template.sep,
            "echo": self.llm_echo,
        }
        return payload

    async def stream_call(self):
        # TODO Retry when server connection error
        payload = self.__call_base()

        self.skip_echo_len = len(payload.get("prompt").replace("</s>", " ")) + 11
        logger.info(f"Requert: \n{payload}")
        ai_response_text = ""
        try:
            from pilot.model.cluster import WorkerManagerFactory

            worker_manager = CFG.SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            async for output in worker_manager.generate_stream(payload):
                yield output
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parase faild！" + str(e))
            self.current_message.add_view_message(
                f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
            )
            ### store current conversation
            self.memory.append(self.current_message)

    async def nostream_call(self):
        payload = self.__call_base()
        logger.info(f"Request: \n{payload}")
        ai_response_text = ""
        try:
            from pilot.model.cluster import WorkerManagerFactory

            worker_manager = CFG.SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()

            model_output = await worker_manager.generate(payload)

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
            ###  run
            result = self.do_action(prompt_define_response)

            ### llm speaker
            speak_to_user = self.get_llm_speak(prompt_define_response)

            view_message = self.prompt_template.output_parser.parse_view_response(
                speak_to_user, result
            )
            self.current_message.add_view_message(view_message)
        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parase faild！" + str(e))
            self.current_message.add_view_message(
                f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
            )
        ### store dialogue
        self.memory.append(self.current_message)
        return self.current_ai_response()

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
        text += self.__load_system_message()

        ### Load examples
        text += self.__load_example_messages()

        ### Load History
        text += self.__load_histroy_messages()

        ### Load User Input
        text += self.__load_user_message()
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
        messages += self.__load_system_message(str_message=False)
        ### Load examples
        messages += self.__load_example_messages(str_message=False)

        ### Load History
        messages += self.__load_histroy_messages(str_message=False)

        ### Load User Input
        messages += self.__load_user_message(str_message=False)
        return messages

    def __load_system_message(self, str_message: bool = True):
        system_convs = self.current_message.get_system_conv()
        system_text = ""
        system_messages = []
        for system_conv in system_convs:
            system_text += (
                system_conv.type + ":" + system_conv.content + self.prompt_template.sep
            )
            system_messages.append(
                ModelMessage(role=system_conv.type, content=system_conv.content)
            )
        return system_text if str_message else system_messages

    def __load_user_message(self, str_message: bool = True):
        user_conv = self.current_message.get_user_conv()
        user_messages = []
        if user_conv:
            user_text = (
                user_conv.type + ":" + user_conv.content + self.prompt_template.sep
            )
            user_messages.append(
                ModelMessage(role=user_conv.type, content=user_conv.content)
            )
            return user_text if str_message else user_messages
        else:
            raise ValueError("Hi! What do you want to talk about？")

    def __load_example_messages(self, str_message: bool = True):
        example_text = ""
        example_messages = []
        if self.prompt_template.example_selector:
            for round_conv in self.prompt_template.example_selector.examples():
                for round_message in round_conv["messages"]:
                    if not round_message["type"] in [
                        ModelMessageRoleType.VIEW,
                        ModelMessageRoleType.SYSTEM,
                    ]:
                        message_type = round_message["type"]
                        message_content = round_message["data"]["content"]
                        example_text += (
                            message_type
                            + ":"
                            + message_content
                            + self.prompt_template.sep
                        )
                        example_messages.append(
                            ModelMessage(role=message_type, content=message_content)
                        )
        return example_text if str_message else example_messages

    def __load_histroy_messages(self, str_message: bool = True):
        history_text = ""
        history_messages = []
        if self.prompt_template.need_historical_messages:
            if self.history_message:
                logger.info(
                    f"There are already {len(self.history_message)} rounds of conversations! Will use {self.chat_retention_rounds} rounds of content as history!"
                )
            if len(self.history_message) > self.chat_retention_rounds:
                for first_message in self.history_message[0]["messages"]:
                    if not first_message["type"] in [ModelMessageRoleType.VIEW]:
                        message_type = first_message["type"]
                        message_content = first_message["data"]["content"]
                        history_text += (
                            message_type
                            + ":"
                            + message_content
                            + self.prompt_template.sep
                        )
                        history_messages.append(
                            ModelMessage(role=message_type, content=message_content)
                        )
                if self.chat_retention_rounds > 1:
                    index = self.chat_retention_rounds - 1
                    for round_conv in self.history_message[-index:]:
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
                                    + self.prompt_template.sep
                                )
                                history_messages.append(
                                    ModelMessage(
                                        role=message_type, content=message_content
                                    )
                                )

            else:
                ### user all history
                for conversation in self.history_message:
                    for message in conversation["messages"]:
                        ### histroy message not have promot and view info
                        if not message["type"] in [
                            ModelMessageRoleType.VIEW,
                            ModelMessageRoleType.SYSTEM,
                        ]:
                            message_type = message["type"]
                            message_content = message["data"]["content"]
                            history_text += (
                                message_type
                                + ":"
                                + message_content
                                + self.prompt_template.sep
                            )
                            history_messages.append(
                                ModelMessage(role=message_type, content=message_content)
                            )

        return history_text if str_message else history_messages

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
