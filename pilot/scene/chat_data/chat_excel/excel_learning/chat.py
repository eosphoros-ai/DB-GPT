import json
import os

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
from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader
from pilot.json_utils.utilities import DateTimeEncoder

CFG = Config()


class ExcelLearning(BaseChat):
    chat_scene: str = ChatScene.ExcelLearning.value()

    def __init__(self, chat_session_id, user_input, select_param:str=None):
        chat_mode = ChatScene.ExcelLearning
        """ """
        self.excel_file_path = select_param
        self.excel_reader = ExcelReader(select_param)
        super().__init__(
            chat_mode=chat_mode,
            chat_session_id=chat_session_id,
            current_user_input = user_input,
            select_param=select_param,
        )


    def generate_input_values(self):

        colunms, datas = self.excel_reader.get_sample_data()
        datas.insert(0, colunms)

        input_values = {
            "data_example": json.dumps(self.excel_reader.get_sample_data(), cls=DateTimeEncoder),
        }
        return input_values


