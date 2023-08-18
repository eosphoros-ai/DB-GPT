import json
import os

from pilot.scene.base_message import (
    HumanMessage,
    ViewMessage,
)
from pilot.scene.base_chat import BaseChat, logger
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.common.markdown_text import (
    generate_htm_table,
)
from pilot.scene.chat_data.chat_excel.excel_learning.prompt import prompt
from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader

CFG = Config()


class ExcelLearning(BaseChat):
    chat_scene: str = ChatScene.ChatExcel.value()

    def __init__(self, chat_session_id, user_input, select_param: str = ""):
        chat_mode = ChatScene.ChatExcel

        self.excel_file_path = select_param
        file_name, file_extension = os.path.splitext(select_param)
        self.excel_file_name = file_name
        self.excel_reader = ExcelReader(select_param)

        super().__init__(
            chat_mode=chat_mode,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
            select_param=select_param,
        )

    def generate_input_values(self):

        input_values = {
            "data_example": json.dumps(self.excel_reader.get_sample_data()),
        }
        return input_values

    def prepare(self):
        logger.info(f"{self.chat_mode} prepare start!")
        chat_param = {
            "chat_session_id": self.chat_session_id,
            "user_input": self.excel_file_name + " analysis！",
            "select_param": self.excel_file_path
        }
        chat: BaseChat = ExcelLearning(**chat_param)

        return chat.call()


    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")
        param= {
            "speak": prompt_response["thoughts"],
            "df": self.excel_reader.get_df_by_sql(prompt_response["sql"])
        }
        return CFG.command_disply.call(prompt_response['display'], **param)

