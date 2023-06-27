import time
from abc import ABC, abstractmethod
import datetime
import traceback
import json
from pydantic import BaseModel, Field, root_validator, validator, Extra
from typing import (
    Any,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)
import requests
from urllib.parse import urljoin

import pilot.configs.config
from pilot.scene.message import OnceConversation
from pilot.prompts.prompt_new import PromptTemplate
from pilot.memory.chat_history.base import BaseChatHistoryMemory
from pilot.memory.chat_history.file_history import FileHistoryMemory
from pilot.memory.chat_history.mem_history import MemHistoryMemory
from pilot.memory.chat_history.duckdb_history import DuckdbHistoryMemory

from pilot.configs.model_config import LOGDIR, DATASETS_DIR
from pilot.utils import (
    build_logger,
    server_error_msg,
)
from pilot.scene.base_message import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    ViewMessage,
)
from pilot.configs.config import Config

logger = build_logger("BaseChat", LOGDIR + "BaseChat.log")
headers = {"User-Agent": "dbgpt Client"}
CFG = Config()


class BaseChat(ABC):
    chat_scene: str = None
    llm_model: Any = None
    temperature: float = 0.6
    max_new_tokens: int = 1024
    # By default, keep the last two rounds of conversation records as the context
    chat_retention_rounds: int = 2

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        chat_mode,
        chat_session_id,
        current_user_input,
    ):
        self.chat_session_id = chat_session_id
        self.chat_mode = chat_mode
        self.current_user_input: str = current_user_input
        self.llm_model = CFG.LLM_MODEL
        ### can configurable storage methods
        self.memory = DuckdbHistoryMemory(chat_session_id)

        ### load prompt template
        self.prompt_template: PromptTemplate = CFG.prompt_templates[
            self.chat_mode.value
        ]
        self.history_message: List[OnceConversation] = self.memory.messages()
        self.current_message: OnceConversation = OnceConversation(chat_mode.value)
        self.current_tokens_used: int = 0
        ### load chat_session_id's chat historys
        self._load_history(self.chat_session_id)

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

    def __call_base(self):
        input_values = self.generate_input_values()
        ### Chat sequence advance
        self.current_message.chat_order = len(self.history_message) + 1
        self.current_message.add_user_message(self.current_user_input)
        self.current_message.start_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # TODO
        self.current_message.tokens = 0
        current_prompt = None

        if self.prompt_template.template:
            current_prompt = self.prompt_template.format(**input_values)

        ### 构建当前对话， 是否安第一次对话prompt构造？ 是否考虑切换库
        if self.history_message:
            ## TODO 带历史对话记录的场景需要确定切换库后怎么处理
            logger.info(
                f"There are already {len(self.history_message)} rounds of conversations!"
            )
        if current_prompt:
            self.current_message.add_system_message(current_prompt)

        payload = {
            "model": self.llm_model,
            "prompt": self.generate_llm_text(),
            "temperature": float(self.temperature),
            "max_new_tokens": int(self.max_new_tokens),
            "stop": self.prompt_template.sep,
        }
        return payload

    def stream_call(self):
        # TODO Retry when server connection error
        payload = self.__call_base()

        self.skip_echo_len = len(payload.get("prompt").replace("</s>", " ")) + 11
        logger.info(f"Requert: \n{payload}")
        ai_response_text = ""
        try:
            show_info = ""
            response = requests.post(
                urljoin(CFG.MODEL_SERVER, "generate_stream"),
                headers=headers,
                json=payload,
                stream=True,
                timeout=120,
            )
            return response

            # yield self.prompt_template.output_parser.parse_model_stream_resp(response, skip_echo_len)

            # for resp_text_trunck in ai_response_text:
            #     show_info = resp_text_trunck
            #     yield resp_text_trunck + "▌"

            self.current_message.add_ai_message(show_info)

        except Exception as e:
            print(traceback.format_exc())
            logger.error("model response parase faild！" + str(e))
            self.current_message.add_view_message(
                f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
            )
        ### 对话记录存储
        self.memory.append(self.current_message)

    def nostream_call(self):
        payload = self.__call_base()
        logger.info(f"Requert: \n{payload}")
        ai_response_text = ""
        try:
            ### 走非流式的模型服务接口
            response = requests.post(
                urljoin(CFG.MODEL_SERVER, "generate"),
                headers=headers,
                json=payload,
                timeout=120,
            )

            ### output parse
            ai_response_text = (
                self.prompt_template.output_parser.parse_model_nostream_resp(
                    response, self.prompt_template.sep
                )
            )

            #             ### MOCK
            #             ai_response_text = """{
            # "thoughts": "可以从users表和tran_order表联合查询，按城市和订单数量进行分组统计，并使用柱状图展示。",
            # "reasoning": "为了分析用户在不同城市的分布情况，需要查询users表和tran_order表，使用LEFT JOIN将两个表联合起来。按照城市进行分组，统计每个城市的订单数量。使用柱状图展示可以直观地看出每个城市的订单数量，方便比较。",
            # "speak": "根据您的分析目标，我查询了用户表和订单表，统计了每个城市的订单数量，并生成了柱状图展示。",
            # "command": {
            # "name": "histogram-executor",
            # "args": {
            # "title": "订单城市分布柱状图",
            # "sql": "SELECT users.city, COUNT(tran_order.order_id) AS order_count FROM users LEFT JOIN tran_order ON users.user_name = tran_order.user_name GROUP BY users.city"
            # }
            # }
            # }"""

            self.current_message.add_ai_message(ai_response_text)
            prompt_define_response = self.prompt_template.output_parser.parse_prompt_response(ai_response_text)


            result = self.do_action(prompt_define_response)

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
        ### 对话记录存储
        self.memory.append(self.current_message)
        return self.current_ai_response()

    def call(self):
        if self.prompt_template.stream_out:
            yield self.stream_call()
        else:
            return self.nostream_call()

    def generate_llm_text(self) -> str:
        text = ""
        if self.prompt_template.template_define:
            text = self.prompt_template.template_define + self.prompt_template.sep

        ### 处理历史信息
        if len(self.history_message) > self.chat_retention_rounds:
            ### 使用历史信息的第一轮和最后n轮数据合并成历史对话记录, 做上下文提示时，用户展示消息需要过滤掉
            for first_message in self.history_message[0].messages:
                if not isinstance(first_message, ViewMessage):
                    text += (
                        first_message.type
                        + ":"
                        + first_message.content
                        + self.prompt_template.sep
                    )

            index = self.chat_retention_rounds - 1
            for last_message in self.history_message[-index:].messages:
                if not isinstance(last_message, ViewMessage):
                    text += (
                        last_message.type
                        + ":"
                        + last_message.content
                        + self.prompt_template.sep
                    )

        else:
            ### 直接历史记录拼接
            for conversation in self.history_message:
                for message in conversation.messages:
                    if not isinstance(message, ViewMessage):
                        text += (
                            message.type
                            + ":"
                            + message.content
                            + self.prompt_template.sep
                        )
        ### current conversation

        for now_message in self.current_message.messages:
            text += (
                now_message.type + ":" + now_message.content + self.prompt_template.sep
            )

        return text

    # 暂时为了兼容前端
    def current_ai_response(self) -> str:
        for message in self.current_message.messages:
            if message.type == "view":
                return message.content
        return None

    def _load_history(self, session_id: str) -> List[OnceConversation]:
        """
        load chat history by session_id
        Args:
            session_id:
        Returns:
        """
        return self.memory.messages()

    def generate(self, p) -> str:
        """
        generate context for LLM input
        Args:
            p:

        Returns:

        """
        pass
