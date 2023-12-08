import os
import logging

from typing import Dict
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt._private.config import Config
from dbgpt.agent.commands.command_mange import ApiCall
from dbgpt.app.scene.chat_data.chat_excel.excel_reader import ExcelReader
from dbgpt.app.scene.chat_data.chat_excel.excel_learning.chat import ExcelLearning
from dbgpt.util.path_utils import has_path
from dbgpt.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH
from dbgpt.util.tracer import root_tracer, trace

CFG = Config()

logger = logging.getLogger(__name__)


class ChatExcel(BaseChat):
    """a Excel analyzer to analyze Excel Data"""

    chat_scene: str = ChatScene.ChatExcel.value()
    chat_retention_rounds = 2

    def __init__(self, chat_param: Dict):
        """Chat Excel Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) file path
        """
        chat_mode = ChatScene.ChatExcel

        self.select_param = chat_param["select_param"]
        self.model_name = chat_param["model_name"]
        chat_param["chat_mode"] = ChatScene.ChatExcel
        if has_path(self.select_param):
            self.excel_reader = ExcelReader(self.select_param)
        else:
            self.excel_reader = ExcelReader(
                os.path.join(
                    KNOWLEDGE_UPLOAD_ROOT_PATH, chat_mode.value(), self.select_param
                )
            )
        self.api_call = ApiCall(display_registry=CFG.command_disply)
        super().__init__(chat_param=chat_param)

    @trace()
    async def generate_input_values(self) -> Dict:
        input_values = {
            "user_input": self.current_user_input,
            "table_name": self.excel_reader.table_name,
            "disply_type": self._generate_numbered_list(),
        }
        return input_values

    async def prepare(self):
        logger.info(f"{self.chat_mode} prepare start!")
        if len(self.history_message) > 0:
            return None
        chat_param = {
            "chat_session_id": self.chat_session_id,
            "user_input": "[" + self.excel_reader.excel_file_name + "]" + " Analyze！",
            "parent_mode": self.chat_mode,
            "select_param": self.excel_reader.excel_file_name,
            "excel_reader": self.excel_reader,
            "model_name": self.model_name,
        }
        learn_chat = ExcelLearning(**chat_param)
        result = await learn_chat.nostream_call()
        return result

    def stream_plugin_call(self, text):
        text = (
            text.replace("\\n", " ")
            .replace("\n", " ")
            .replace("\_", "_")
            .replace("\\", " ")
        )
        with root_tracer.start_span(
            "ChatExcel.stream_plugin_call.run_display_sql", metadata={"text": text}
        ):
            return self.api_call.display_sql_llmvis(
                text, self.excel_reader.get_df_by_sql_ex
            )
