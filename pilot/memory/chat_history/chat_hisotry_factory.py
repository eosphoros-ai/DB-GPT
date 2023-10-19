from .base import MemoryStoreType
from pilot.configs.config import Config

CFG = Config()


class ChatHistory:
    def __init__(self):
        self.memory_type = MemoryStoreType.DB.value
        self.mem_store_class_map = {}
        from .store_type.duckdb_history import DuckdbHistoryMemory
        from .store_type.file_history import FileHistoryMemory
        from .store_type.meta_db_history import DbHistoryMemory
        from .store_type.mem_history import MemHistoryMemory

        self.mem_store_class_map[DuckdbHistoryMemory.store_type] = DuckdbHistoryMemory
        self.mem_store_class_map[FileHistoryMemory.store_type] = FileHistoryMemory
        self.mem_store_class_map[DbHistoryMemory.store_type] = DbHistoryMemory
        self.mem_store_class_map[MemHistoryMemory.store_type] = MemHistoryMemory

    def get_store_instance(self, chat_session_id):
        return self.mem_store_class_map.get(CFG.CHAT_HISTORY_STORE_TYPE)(
            chat_session_id
        )

    def get_store_cls(self):
        return self.mem_store_class_map.get(CFG.CHAT_HISTORY_STORE_TYPE)
