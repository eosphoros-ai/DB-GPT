import json
import os
import asyncio

from typing import List, Any, Dict
from pilot.scene.base_chat import BaseChat, logger
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config

from pilot.scene.chat_data.chat_excel.excel_analyze.prompt import prompt
from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader
from pilot.scene.chat_data.chat_excel.excel_learning.chat import ExcelLearning
from pilot.common.path_utils import has_path
from pilot.configs.model_config import LLM_MODEL_CONFIG, KNOWLEDGE_UPLOAD_ROOT_PATH


CFG = Config()


class ChatExcel(BaseChat):
    chat_scene: str = ChatScene.ChatExcel.value()
    chat_retention_rounds = 1

    def __init__(self, chat_param: Dict):
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

        super().__init__(chat_param=chat_param)

    def _generate_command_string(self, command: Dict[str, Any]) -> str:
        """
        Generate a formatted string representation of a command.

        Args:
            command (dict): A dictionary containing command information.

        Returns:
            str: The formatted command string.
        """
        args_string = ", ".join(
            f'"{key}": "{value}"' for key, value in command["args"].items()
        )
        return f'{command["label"]}: "{command["name"]}", args: {args_string}'

    def _generate_numbered_list(self) -> str:
        command_strings = []
        if CFG.command_disply:
            command_strings += [
                str(item)
                for item in CFG.command_disply.commands.values()
                if item.enabled
            ]
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(command_strings))

    def generate_input_values(self):
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
            "user_input": "[" + self.excel_reader.excel_file_name + "]" + " Analysis！",
            "parent_mode": self.chat_mode,
            "select_param": self.excel_reader.excel_file_name,
            "excel_reader": self.excel_reader,
            "model_name": self.model_name,
        }
        learn_chat = ExcelLearning(**chat_param)
        result = await learn_chat.nostream_call()
        return result

    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")

        # colunms, datas = self.excel_reader.run(prompt_response.sql)
        param = {
            "speak": prompt_response.thoughts,
            "df": self.excel_reader.get_df_by_sql_ex(prompt_response.sql),
        }
        if CFG.command_disply.get_command(prompt_response.display):
            return CFG.command_disply.call(prompt_response.display, **param)
        else:
            return CFG.command_disply.call("response_table", **param)
