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
import pymysql
from datetime import datetime



CFG = Config()


class MysqlHistoryMemory(BaseChatHistoryMemory):
    def __init__(self, chat_session_id: str):
        self.chat_seesion_id = chat_session_id
        self.connect = pymysql.connect(
            host=CFG.LOCAL_DB_HOST,
            user=CFG.LOCAL_DB_USER,
            password=CFG.LOCAL_DB_PASSWORD,
            database='history'
        )


    def __get_messages_by_conv_uid(self, conv_uid: str):
        cursor = self.connect.cursor()
        cursor.execute("SELECT messages FROM chat_history where conv_uid= %s ", (conv_uid))
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
            now = datetime.now()
            formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "INSERT INTO chat_history(conv_uid, chat_mode, summary, user_name, messages, gmt_created, gmt_modified)VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (self.chat_seesion_id, chat_mode, summary, user_name, "", formatted_date, formatted_date)
            )
            self.connect.commit()
        except Exception as e:
            print("init create conversation log error！" + str(e))

    def append(self, once_message: OnceConversation) -> None:
        context = self.__get_messages_by_conv_uid(self.chat_seesion_id)
        conversations: List[OnceConversation] = []
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')
        if context:
            conversations = json.loads(context)
        conversations.append(_conversation_to_dic(once_message))
        cursor = self.connect.cursor()
        if context:
            cursor.execute(
                "UPDATE chat_history set messages=%s , gmt_modified =%s where conv_uid= %s",
                (json.dumps(conversations, ensure_ascii=False), formatted_date, self.chat_seesion_id)
            )
        else:
            cursor.execute(
                "INSERT INTO chat_history(conv_uid, chat_mode,  summary, user_name, messages,gmt_created, gmt_modified )VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.chat_seesion_id,
                    once_message.chat_mode,
                    once_message.get_user_conv().content,
                    "",
                    json.dumps(conversations, ensure_ascii=False),
                    formatted_date,
                    formatted_date
                ),
            )
        self.connect.commit()

    def clear(self) -> None:
        cursor = self.connect.cursor()
        cursor.execute(
            "DELETE FROM chat_history where conv_uid= %s", (self.chat_seesion_id)
        )
        self.connect.commit()

    def delete(self) -> bool:
        cursor = self.connect.cursor()
        cursor.execute(
            "DELETE FROM chat_history where conv_uid= %s", (self.chat_seesion_id)
        )
        self.connect.commit()
        return True


    @staticmethod
    def conv_list(cls, user_name: str = None) -> None:
        connect = pymysql.connect(
            host=CFG.LOCAL_DB_HOST,
            user=CFG.LOCAL_DB_USER,
            password=CFG.LOCAL_DB_PASSWORD,
            database='history'
        )
        cursor = connect.cursor()
        cursor.execute("SELECT * FROM chat_history order by gmt_created desc limit 20")
        # 获取查询结果字段名
        fields = [field[0] for field in cursor.description]
        data = []
        for row in cursor.fetchall():
            row_dict = {}
            for i, field in enumerate(fields):
                row_dict[field] = row[i]
            data.append(row_dict)
        return data


    def get_messages(self) -> List[OnceConversation]:
        cursor = self.connect.cursor()
        cursor.execute(
            "SELECT messages FROM chat_history where conv_uid= %s", (self.chat_seesion_id)
        )
        context = cursor.fetchone()
        if context:
            if context[0]:
                return json.loads(context[0])
        return None
