from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config
from pilot.scene.chat_db.professional_qa.prompt import prompt

CFG = Config()


class ChatWithDbQA(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbQA.value()

    """Number of results to return from the query"""

    def __init__(self, chat_param: Dict):
        """ """
        self.db_name = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatWithDbQA
        super().__init__(chat_param=chat_param)

        if self.db_name:
            self.database = CFG.LOCAL_DB_MANAGE.get_connect(self.db_name)
            self.db_connect = self.database.session
            self.tables = self.database.get_table_names()

        self.top_k = (
            CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            if len(self.tables) > CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            else len(self.tables)
        )

    def generate_input_values(self):
        table_info = ""
        dialect = "mysql"
        try:
            from pilot.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        if self.db_name:
            client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
            try:
                table_infos = client.get_db_summary(
                    dbname=self.db_name, query=self.current_user_input, topk=self.top_k
                )
            except Exception as e:
                print("db summary find error!" + str(e))
                table_infos = self.database.table_simple_info()

            # table_infos = self.database.table_simple_info()
            dialect = self.database.dialect

        input_values = {
            "input": self.current_user_input,
            # "top_k": str(self.top_k),
            # "dialect": dialect,
            "table_info": table_infos,
        }
        return input_values
