from dbgpt.component import SystemApp, BaseComponent, ComponentType

from .db_manager import DatabaseManager


class UnifiedDBManagerFactory(BaseComponent):
    name = ComponentType.UNIFIED_METADATA_DB_MANAGER_FACTORY

    def __init__(self, system_app: SystemApp, db_manager: DatabaseManager):
        super().__init__(system_app)
        self._db_manager = db_manager

    def init_app(self, system_app: SystemApp):
        pass

    def create(self) -> DatabaseManager:
        if not self._db_manager:
            raise RuntimeError("db_manager is not initialized")
        if not self._db_manager.is_initialized:
            raise RuntimeError("db_manager is not initialized")
        return self._db_manager
