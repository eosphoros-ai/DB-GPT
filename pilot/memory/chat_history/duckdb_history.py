import json
import os
import duckdb
from typing import List

from pilot.configs.config import Config
from pilot.memory.chat_history.base import BaseChatHistoryMemory
from pilot.scene.message import (
    OnceConversation,
    conversation_from_dict,
    _conversation_to_dic,
    conversations_to_dict,
)
from pilot.common.formatting import MyEncoder

default_db_path = os.path.join(os.getcwd(), "message")
duckdb_path = os.getenv("DB_DUCKDB_PATH", default_db_path + "/chat_history.db")
table_name = "chat_history"

CFG = Config()


class DuckdbHistoryMemory(BaseChatHistoryMemory):
    def __init__(self, chat_session_id: str):
        self.chat_seesion_id = chat_session_id
        os.makedirs(default_db_path, exist_ok=True)
        self.connect = duckdb.connect(duckdb_path)
        self.__init_chat_history_tables()

    def __init_chat_history_tables(self):
        # 检查表是否存在
        result = self.connect.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table_name]
        ).fetchall()

        if not result:
            # 如果表不存在，则创建新表
            self.connect.execute(
                "CREATE TABLE chat_history (id integer primary key, conv_uid VARCHAR(100) UNIQUE, chat_mode VARCHAR(50), summary VARCHAR(255),  user_name VARCHAR(100), messages TEXT)"
            )
            self.connect.execute("CREATE SEQUENCE seq_id START 1;")

    def __get_messages_by_conv_uid(self, conv_uid: str):
        cursor = self.connect.cursor()
        cursor.execute("SELECT messages FROM chat_history where conv_uid=?", [conv_uid])
        content = cursor.fetchone()
        if content:
            return content[0]
        else:
            return None

    def messages(self) -> List[OnceConversation]:
        context = self.__get_messages_by_conv_uid(self.chat_seesion_id)
        if context:
            conversations: List[OnceConversation] = json.loads(context)
            return conversations
        return []

    def create(self, chat_mode, summary: str, user_name: str) -> None:
        try:
            cursor = self.connect.cursor()
            cursor.execute(
                "INSERT INTO chat_history(id, conv_uid, chat_mode summary, user_name, messages)VALUES(nextval('seq_id'),?,?,?,?,?)",
                [self.chat_seesion_id, chat_mode, summary, user_name, ""],
            )
            cursor.commit()
            self.connect.commit()
        except Exception as e:
            print("init create conversation log error！" + str(e))

    def append(self, once_message: OnceConversation) -> None:
        context = self.__get_messages_by_conv_uid(self.chat_seesion_id)
        conversations: List[OnceConversation] = []
        if context:
            conversations = json.loads(context)
        conversations.append(_conversation_to_dic(once_message))
        cursor = self.connect.cursor()
        if context:
            cursor.execute(
                "UPDATE chat_history set messages=? where conv_uid=?",
                [json.dumps(conversations, ensure_ascii=False), self.chat_seesion_id],
            )
        else:
            cursor.execute(
                "INSERT INTO chat_history(id, conv_uid, chat_mode,  summary, user_name, messages)VALUES(nextval('seq_id'),?,?,?,?,?)",
                [
                    self.chat_seesion_id,
                    once_message.chat_mode,
                    once_message.get_user_conv().content,
                    "",
                    json.dumps(conversations, ensure_ascii=False),
                ],
            )
        cursor.commit()
        self.connect.commit()

    def clear(self) -> None:
        cursor = self.connect.cursor()
        cursor.execute(
            "DELETE FROM chat_history where conv_uid=?", [self.chat_seesion_id]
        )
        cursor.commit()
        self.connect.commit()

    def delete(self) -> bool:
        cursor = self.connect.cursor()
        cursor.execute(
            "DELETE FROM chat_history where conv_uid=?", [self.chat_seesion_id]
        )
        cursor.commit()
        return True

    @staticmethod
    def conv_list(cls, user_name: str = None) -> None:
        if os.path.isfile(duckdb_path):
            cursor = duckdb.connect(duckdb_path).cursor()
            if user_name:
                cursor.execute(
                    "SELECT * FROM chat_history where user_name=? order by id desc limit 20",
                    [user_name],
                )
            else:
                cursor.execute("SELECT * FROM chat_history order by id desc limit 20")
            # 获取查询结果字段名
            fields = [field[0] for field in cursor.description]
            data = []
            for row in cursor.fetchall():
                row_dict = {}
                for i, field in enumerate(fields):
                    row_dict[field] = row[i]
                data.append(row_dict)

            return data

        return []

    def get_messages(self) -> List[OnceConversation]:
        cursor = self.connect.cursor()
        cursor.execute(
            "SELECT messages FROM chat_history where conv_uid=?", [self.chat_seesion_id]
        )
        context = cursor.fetchone()
        if context:
            if context[0]:
                return json.loads(context[0])
        return None
