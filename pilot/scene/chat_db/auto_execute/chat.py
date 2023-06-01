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
from pilot.scene.chat_db.auto_execute.prompt import prompt

CFG = Config()


class ChatWithDbAutoExecute(BaseChat):
    chat_scene: str = ChatScene.ChatWithDbExecute.value

    """Number of results to return from the query"""

    def __init__(self,temperature, max_new_tokens, chat_session_id, db_name, user_input):
        """ """
        super().__init__(temperature=temperature,
                         max_new_tokens=max_new_tokens,
                         chat_mode=ChatScene.ChatWithDbExecute,
                         chat_session_id=chat_session_id,
                         current_user_input=user_input)
        if not db_name:
            raise ValueError(f"{ChatScene.ChatWithDbExecute.value} mode should chose db!")
        self.db_name = db_name
        self.database = CFG.local_db
        # 准备DB信息(拿到指定库的链接)
        self.db_connect = self.database.get_session(self.db_name)
        self.top_k: int = 5

    def generate_input_values(self):
        try:
            from pilot.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError(
                "Could not import DBSummaryClient. "
            )
        input_values = {
            "input": self.current_user_input,
            "top_k": str(self.top_k),
            "dialect": self.database.dialect,
            # "table_info": self.database.table_simple_info(self.db_connect)
            "table_info": DBSummaryClient.get_similar_tables(dbname=self.db_name, query=self.current_user_input, topk=self.top_k)
        }
        return input_values

    def do_with_prompt_response(self, prompt_response):
        return self.database.run(self.db_connect, prompt_response.sql)



if __name__ == "__main__":
    db = CFG.local_db
    connect = db.get_session("gpt-user")

    results = db.run(connect, """SELECT user_name, phone, email, city, create_time, last_login_time
        FROM `gpt-user`.users
        WHERE user_name='test1';
        """)

    print(str(db.get_session_db(connect)))
    print(str(results))
    results = db.run(connect, """SELECT user_name, phone, email, city, create_time, last_login_time
        FROM `gpt-user`.users
        WHERE user_name='test2';
        """)
    print(str(db.get_session_db(connect)))
    print(str(results))

    results = db.run(connect, """INSERT INTO `gpt-user`.users
        (user_name, phone, email, city, create_time, last_login_time)
        VALUES('test4', '23', NULL, '成都', '2023-05-09 09:09:09', NULL);
        """)
    print(str(db.get_session_db(connect)))
    print(str(results))

    results = db.run(connect, """SELECT user_name, phone, email, city, create_time, last_login_time
        FROM `gpt-user`.users
        WHERE user_name='test3';
        """)
    print(str(db.get_session_db(connect)))
    print(str(results))