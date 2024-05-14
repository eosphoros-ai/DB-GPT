"""UnifiedDBManagerFactory is a factory class to create a DatabaseManager instance."""
from dbgpt.component import BaseComponent, ComponentType, SystemApp

from .db_manager import DatabaseManager


class UnifiedDBManagerFactory(BaseComponent):
    """UnfiedDBManagerFactory class."""

    name = ComponentType.UNIFIED_METADATA_DB_MANAGER_FACTORY
    """The name of the factory."""

    def __init__(self, system_app: SystemApp, db_manager: DatabaseManager):
        """Create a UnifiedDBManagerFactory instance."""
        super().__init__(system_app)
        self._db_manager = db_manager

    def init_app(self, system_app: SystemApp):
        """Initialize the factory with the system app."""
        pass

    def create(self) -> DatabaseManager:
        """Create a DatabaseManager instance."""
        if not self._db_manager:
            raise RuntimeError("db_manager is not initialized")
        if not self._db_manager.is_initialized:
            raise RuntimeError("db_manager is not initialized")
        return self._db_manager
