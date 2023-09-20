import json
import os
from typing import Any

from pilot.scene.base_message import (
    HumanMessage,
    ViewMessage,
)
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.scene.chat_data.chat_excel.excel_learning.prompt import prompt
from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader
from pilot.json_utils.utilities import DateTimeEncoder

CFG = Config()


class ExcelLearning(BaseChat):
    chat_scene: str = ChatScene.ExcelLearning.value()

    def __init__(
        self,
        chat_session_id,
        user_input,
        parent_mode: Any = None,
        select_param: str = None,
        excel_reader: Any = None,
        model_name: str = None,
    ):
        chat_mode = ChatScene.ExcelLearning
        """ """
        self.excel_file_path = select_param
        self.excel_reader = excel_reader
        chat_param = {
            "chat_mode": chat_mode,
            "chat_session_id": chat_session_id,
            "current_user_input": user_input,
            "select_param": select_param,
            "model_name": model_name,
        }
        super().__init__(chat_param=chat_param)
        if parent_mode:
            self.current_message.chat_mode = parent_mode.value()

    def generate_input_values(self):
        colunms, datas = self.excel_reader.get_sample_data()
        datas.insert(0, colunms)

        input_values = {
            "data_example": json.dumps(
                self.excel_reader.get_sample_data(), cls=DateTimeEncoder
            ),
        }
        return input_values
