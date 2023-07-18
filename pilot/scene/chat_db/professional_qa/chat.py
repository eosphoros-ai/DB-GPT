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
from pilot.scene.chat_db.professional_qa.prompt import prompt

CFG = Config()


class ChatWithDbQA(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbQA.value()

    """Number of results to return from the query"""

    def __init__(self, chat_session_id, db_name, user_input):
        """ """
        super().__init__(
            chat_mode=ChatScene.ChatWithDbQA,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )
        self.db_name = db_name
        if db_name:
            self.database = CFG.local_db
            # 准备DB信息(拿到指定库的链接)
            self.db_connect = self.database.get_session(self.db_name)
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
            client = DBSummaryClient()
            table_info = client.get_db_summary(
                dbname=self.db_name, query=self.current_user_input, topk=self.top_k
            )
            # table_info = self.database.table_simple_info(self.db_connect)
            dialect = self.database.dialect

        input_values = {
            "input": self.current_user_input,
            # "top_k": str(self.top_k),
            # "dialect": dialect,
            "table_info": table_info,
        }
        return input_values
