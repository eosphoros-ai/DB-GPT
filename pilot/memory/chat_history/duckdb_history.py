import json
import os
import duckdb
from typing import List

from pilot.configs.config import Config
from pilot.memory.chat_history.base import BaseChatHistoryMemory
from pilot.scene.message import (
    OnceConversation,
    conversation_from_dict,
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
                "CREATE TABLE chat_history (conv_uid VARCHAR(100) PRIMARY KEY, user_name VARCHAR(100), messages TEXT)"
            )

    def __get_messages_by_conv_uid(self, conv_uid: str):
        cursor = self.connect.cursor()
        cursor.execute("SELECT messages FROM chat_history where conv_uid=?", [conv_uid])
        return cursor.fetchone()

    def messages(self) -> List[OnceConversation]:
        context = self.__get_messages_by_conv_uid(self.chat_seesion_id)
        if context:
            conversations: List[OnceConversation] = json.loads(context[0])
            return conversations
        return []

    def append(self, once_message: OnceConversation) -> None:
        context = self.__get_messages_by_conv_uid(self.chat_seesion_id)
        conversations: List[OnceConversation] = []
        if context:
            conversations = json.load(context)
        conversations.append(once_message)
        cursor = self.connect.cursor()
        if context:
            cursor.execute(
                "UPDATE chat_history set messages=? where conv_uid=?",
                [
                    json.dumps(
                        conversations_to_dict(conversations),
                        ensure_ascii=False,
                        indent=4,
                    ),
                    self.chat_seesion_id,
                ],
            )
        else:
            cursor.execute(
                "INSERT INTO chat_history(conv_uid, user_name, messages)VALUES(?,?,?)",
                [
                    self.chat_seesion_id,
                    "",
                    json.dumps(
                        conversations_to_dict(conversations),
                        ensure_ascii=False,
                        indent=4,
                    ),
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
                    "SELECT * FROM chat_history where user_name=? limit 20", [user_name]
                )
            else:
                cursor.execute("SELECT * FROM chat_history limit 20")
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
            return json.loads(context[0])
        return None
