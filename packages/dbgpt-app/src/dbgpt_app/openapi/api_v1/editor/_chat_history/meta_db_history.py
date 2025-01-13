import json
import logging
from typing import Dict, List, Optional

from dbgpt._private.config import Config
from dbgpt.core.interface.message import OnceConversation, _conversation_to_dict
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryDao, ChatHistoryEntity

from .base import BaseChatHistoryMemory, MemoryStoreType

CFG = Config()
logger = logging.getLogger(__name__)


class DbHistoryMemory(BaseChatHistoryMemory):
    """Db history memory storage.

    It is deprecated.
    """

    store_type: str = MemoryStoreType.DB.value  # type: ignore

    def __init__(self, chat_session_id: str):
        self.chat_seesion_id = chat_session_id
        self.chat_history_dao = ChatHistoryDao()

    def messages(self) -> List[OnceConversation]:
        chat_history: Optional[ChatHistoryEntity] = self.chat_history_dao.get_by_uid(
            self.chat_seesion_id
        )
        if chat_history:
            context = chat_history.messages
            if context:
                conversations: List[OnceConversation] = json.loads(
                    context  # type: ignore
                )
                return conversations
        return []

    # def create(self, chat_mode, summary: str, user_name: str) -> None:
    #     try:
    #         chat_history: ChatHistoryEntity = ChatHistoryEntity()
    #         chat_history.chat_mode = chat_mode
    #         chat_history.summary = summary
    #         chat_history.user_name = user_name
    #
    #         self.chat_history_dao.raw_update(chat_history)
    #     except Exception as e:
    #         logger.error("init create conversation log error！" + str(e))
    #
    def append(self, once_message: OnceConversation) -> None:
        logger.debug(f"db history append: {once_message}")
        chat_history: Optional[ChatHistoryEntity] = self.chat_history_dao.get_by_uid(
            self.chat_seesion_id
        )
        conversations: List[Dict] = []
        latest_user_message = once_message.get_latest_user_message()
        summary = latest_user_message.content if latest_user_message else ""
        if chat_history:
            context = chat_history.messages
            if context:
                conversations = json.loads(context)  # type: ignore
            else:
                chat_history.summary = summary  # type: ignore
        else:
            chat_history = ChatHistoryEntity()
            chat_history.conv_uid = self.chat_seesion_id  # type: ignore
            chat_history.chat_mode = once_message.chat_mode  # type: ignore
            chat_history.user_name = once_message.user_name  # type: ignore
            chat_history.sys_code = once_message.sys_code  # type: ignore
            chat_history.summary = summary  # type: ignore

        conversations.append(_conversation_to_dict(once_message))
        chat_history.messages = json.dumps(  # type: ignore
            conversations, ensure_ascii=False
        )

        self.chat_history_dao.raw_update(chat_history)

    def update(self, messages: List[OnceConversation]) -> None:
        self.chat_history_dao.update_message_by_uid(
            json.dumps(messages, ensure_ascii=False), self.chat_seesion_id
        )

    def delete(self) -> bool:
        self.chat_history_dao.raw_delete(self.chat_seesion_id)
        return True

    def get_messages(self) -> List[Dict]:
        chat_history = self.chat_history_dao.get_by_uid(self.chat_seesion_id)
        if chat_history:
            context = chat_history.messages
            return json.loads(context)  # type: ignore
        return []

    @staticmethod
    def conv_list(
        user_name: Optional[str] = None, sys_code: Optional[str] = None
    ) -> List[Dict]:
        chat_history_dao = ChatHistoryDao()
        history_list = chat_history_dao.list_last_20(user_name, sys_code)
        result = []
        for history in history_list:
            result.append(history.__dict__)
        return result
