from typing import Type
from .base import MemoryStoreType
from dbgpt._private.config import Config
from dbgpt.storage.chat_history.base import BaseChatHistoryMemory

CFG = Config()

# Import first for auto create table
from .store_type.meta_db_history import DbHistoryMemory


class ChatHistory:
    def __init__(self):
        self.memory_type = MemoryStoreType.DB.value
        self.mem_store_class_map = {}
        from .store_type.duckdb_history import DuckdbHistoryMemory
        from .store_type.file_history import FileHistoryMemory
        from .store_type.mem_history import MemHistoryMemory

        self.mem_store_class_map[DuckdbHistoryMemory.store_type] = DuckdbHistoryMemory
        self.mem_store_class_map[FileHistoryMemory.store_type] = FileHistoryMemory
        self.mem_store_class_map[DbHistoryMemory.store_type] = DbHistoryMemory
        self.mem_store_class_map[MemHistoryMemory.store_type] = MemHistoryMemory

    def get_store_instance(self, chat_session_id: str) -> BaseChatHistoryMemory:
        """New store instance for store chat histories

        Args:
            chat_session_id (str): conversation session id

        Returns:
            BaseChatHistoryMemory: Store instance
        """
        return self.mem_store_class_map.get(CFG.CHAT_HISTORY_STORE_TYPE)(
            chat_session_id
        )

    def get_store_cls(self) -> Type[BaseChatHistoryMemory]:
        return self.mem_store_class_map.get(CFG.CHAT_HISTORY_STORE_TYPE)
