import json
import os


from typing import List, Any, Dict
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
from pilot.scene.chat_data.chat_excel.excel_analyze.prompt import prompt
from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader
from pilot.scene.chat_data.chat_excel.excel_learning.chat import ExcelLearning
CFG = Config()


class ChatExcel(BaseChat):
    chat_scene: str = ChatScene.ChatExcel.value()
    chat_retention_rounds = 2
    def __init__(self, chat_session_id, user_input, select_param: str = ""):
        chat_mode = ChatScene.ChatExcel
        ## TODO TEST
        select_param = "/Users/tuyang.yhj/Downloads/example.xlsx"

        self.excel_file_path = select_param
        self.excel_reader = ExcelReader(select_param)

        super().__init__(
            chat_mode=chat_mode,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
            select_param=select_param,
        )


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
            "user_input":  self.current_user_input,
            "table_name": self.excel_reader.table_name,
            "disply_type": self._generate_numbered_list(),
        }
        return input_values

    def prepare(self):
        logger.info(f"{self.chat_mode} prepare start!")
        if len(self.history_message) > 0:
            return None
        chat_param = {
            "chat_session_id": self.chat_session_id,
            "user_input": "[" + self.excel_reader.excel_file_name + self.excel_reader.extension +"]" + " analysis！",
            "select_param": self.excel_file_path
        }
        learn_chat = ExcelLearning(**chat_param)
        result = learn_chat.nostream_call()
        return result


    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")

        # colunms, datas = self.excel_reader.run(prompt_response.sql)
        param= {
            "speak": prompt_response.thoughts,
            "df": self.excel_reader.get_df_by_sql_ex(prompt_response.sql)
        }
        return CFG.command_disply.call(prompt_response.display, **param)

