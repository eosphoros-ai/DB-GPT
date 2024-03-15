"""Module for chat history factory.

It will remove in the future, just support db store type now.
"""
import logging
from typing import Type

from dbgpt._private.config import Config

from .base import BaseChatHistoryMemory, MemoryStoreType

# Import first for auto create table
from .meta_db_history import DbHistoryMemory

# TODO remove global variable
CFG = Config()
logger = logging.getLogger(__name__)


class ChatHistory:
    def __init__(self):
        self.memory_type = MemoryStoreType.DB.value
        self.mem_store_class_map = {}

        # Just support db store type after v0.4.6
        self.mem_store_class_map[DbHistoryMemory.store_type] = DbHistoryMemory

    def get_store_instance(self, chat_session_id: str) -> BaseChatHistoryMemory:
        """New store instance for store chat histories

        Args:
            chat_session_id (str): conversation session id

        Returns:
            BaseChatHistoryMemory: Store instance
        """
        self._check_store_type(CFG.CHAT_HISTORY_STORE_TYPE)
        return self.mem_store_class_map.get(CFG.CHAT_HISTORY_STORE_TYPE)(
            chat_session_id
        )

    def get_store_cls(self) -> Type[BaseChatHistoryMemory]:
        self._check_store_type(CFG.CHAT_HISTORY_STORE_TYPE)
        return self.mem_store_class_map.get(CFG.CHAT_HISTORY_STORE_TYPE)

    def _check_store_type(self, store_type: str):
        """Check store type

        Raises:
            ValueError: Invalid store type
        """
        if store_type == "memory":
            logger.error(
                "Not support memory store type, just support db store type now"
            )
            raise ValueError(f"Invalid store type: {store_type}")

        if store_type == "file":
            logger.error("Not support file store type, just support db store type now")
            raise ValueError(f"Invalid store type: {store_type}")
        if store_type == "duckdb":
            link1 = (
                "https://docs.dbgpt.site/docs/latest/faq/install#q6-how-to-migrate-meta"
                "-table-chat_history-and-connect_config-from-duckdb-to-sqlite"
            )
            link2 = (
                "https://docs.dbgpt.site/docs/latest/faq/install/#q7-how-to-migrate-"
                "meta-table-chat_history-and-connect_config-from-duckdb-to-mysql"
            )
            logger.error(
                "Not support duckdb store type after v0.4.6, just support db store "
                f"type now, you can migrate your message according to {link1} or {link2}"
            )
            raise ValueError(f"Invalid store type: {store_type}")
