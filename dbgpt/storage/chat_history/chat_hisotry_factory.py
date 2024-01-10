import logging
from typing import Type

from dbgpt._private.config import Config
from dbgpt.storage.chat_history.base import BaseChatHistoryMemory

from .base import MemoryStoreType

# TODO remove global variable
CFG = Config()
logger = logging.getLogger(__name__)

# Import first for auto create table
from .store_type.meta_db_history import DbHistoryMemory


class ChatHistory:
    def __init__(self):
        self.memory_type = MemoryStoreType.DB.value
        self.mem_store_class_map = {}

        # Just support db store type after v0.4.6
        # from .store_type.duckdb_history import DuckdbHistoryMemory
        # from .store_type.file_history import FileHistoryMemory
        # from .store_type.mem_history import MemHistoryMemory
        # self.mem_store_class_map[DuckdbHistoryMemory.store_type] = DuckdbHistoryMemory
        # self.mem_store_class_map[FileHistoryMemory.store_type] = FileHistoryMemory
        # self.mem_store_class_map[MemHistoryMemory.store_type] = MemHistoryMemory

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
        from .store_type.duckdb_history import DuckdbHistoryMemory
        from .store_type.file_history import FileHistoryMemory
        from .store_type.mem_history import MemHistoryMemory

        if store_type == MemHistoryMemory.store_type:
            logger.error(
                "Not support memory store type, just support db store type now"
            )
            raise ValueError(f"Invalid store type: {store_type}")

        if store_type == FileHistoryMemory.store_type:
            logger.error("Not support file store type, just support db store type now")
            raise ValueError(f"Invalid store type: {store_type}")
        if store_type == DuckdbHistoryMemory.store_type:
            link1 = "https://docs.dbgpt.site/docs/faq/install#q6-how-to-migrate-meta-table-chat_history-and-connect_config-from-duckdb-to-sqlitel"
            link2 = "https://docs.dbgpt.site/docs/faq/install#q7-how-to-migrate-meta-table-chat_history-and-connect_config-from-duckdb-to-mysql"
            logger.error(
                "Not support duckdb store type after v0.4.6, just support db store type now, "
                f"you can migrate your message according to {link1} or {link2}"
            )
            raise ValueError(f"Invalid store type: {store_type}")
