import json

from pilot.scene.base_message import (
    HumanMessage,
    ViewMessage,
)
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.common.markdown_text import (
    generate_htm_table,
)
from pilot.scene.chat_data.chat_excel.excel_learning.prompt import prompt

CFG = Config()


class ExcelLearning(BaseChat):
    chat_scene: str = ChatScene.ExcelLearning.value()

    def __init__(self, chat_session_id, file_path):
        chat_mode = ChatScene.ChatWithDbExecute
        """ """
        super().__init__(
            chat_mode=chat_mode,
            chat_session_id=chat_session_id,
            select_param=file_path,
        )


    def generate_input_values(self):

        input_values = {
            "data_example": "",
        }
        return input_values


