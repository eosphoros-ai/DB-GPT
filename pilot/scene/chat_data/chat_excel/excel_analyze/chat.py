import json
import os
import asyncio

from typing import List, Any, Dict
from pilot.scene.base_chat import BaseChat, logger
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.base_modules.agent.commands.command_mange import ApiCall
from pilot.scene.chat_data.chat_excel.excel_analyze.prompt import prompt
from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader
from pilot.scene.chat_data.chat_excel.excel_learning.chat import ExcelLearning
from pilot.common.path_utils import has_path
from pilot.configs.model_config import LLM_MODEL_CONFIG, KNOWLEDGE_UPLOAD_ROOT_PATH
from pilot.base_modules.agent.common.schema import Status

CFG = Config()


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

    def _generate_numbered_list(self) -> str:
        antv_charts = [{"line_chart":"used to display comparative trend analysis data"},
                       {"pie_chart":"suitable for scenarios such as proportion and distribution statistics"},
                       {"response_table":"suitable for display with many display columns or non-numeric columns"},
                       {"data_text":" the default display method, suitable for single-line or simple content display"},
                       {"scatter_plot":"Suitable for exploring relationships between variables, detecting outliers, etc."},
                       {"bubble_chart":"Suitable for relationships between multiple variables, highlighting outliers or special situations, etc."},
                       {"donut_chart":"Suitable for hierarchical structure representation, category proportion display and highlighting key categories, etc."},
                       {"area_chart":"Suitable for visualization of time series data, comparison of multiple groups of data, analysis of data change trends, etc."},
                       {"heatmap":"Suitable for visual analysis of time series data, large-scale data sets, distribution of classified data, etc."}
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
        return "\n".join(f"{key}:{value}" for dict_item in antv_charts for key, value in dict_item.items())

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
            "user_input": f"{self.excel_reader.excel_file_name} analyze！",
            "parent_mode": self.chat_mode,
            "select_param": self.excel_reader.excel_file_name,
            "excel_reader": self.excel_reader,
            "model_name": self.model_name,
        }
        learn_chat = ExcelLearning(**chat_param)
        result = await learn_chat.nostream_call()
        return result

    def stream_plugin_call(self, text):
        text = text.replace("\n", " ")
        return self.api_call.display_sql_llmvis(text, self.excel_reader.get_df_by_sql_ex)
