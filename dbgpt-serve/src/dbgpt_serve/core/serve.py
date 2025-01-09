import logging
from abc import ABC
from typing import Any, Callable, List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.storage.metadata import DatabaseManager

logger = logging.getLogger(__name__)


class BaseServe(BaseComponent, ABC):
    """Base serve component for DB-GPT"""

    name = "dbgpt_serve_base"

    def __init__(
        self,
        system_app: SystemApp,
        api_prefix: str | List[str],
        api_tags: List[str],
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        self._system_app = system_app
        self._api_prefix = api_prefix
        self._api_tags = api_tags
        self._db_url_or_db = db_url_or_db
        self._try_create_tables = try_create_tables
        self._not_create_table = True
        self._app_has_initiated = False

    def create_or_get_db_manager(self) -> DatabaseManager:
        """Create or get the database manager.
        This method must be called after the application is initialized

        Returns:
            DatabaseManager: The database manager
        """
        from dbgpt.storage.metadata import Model, UnifiedDBManagerFactory, db

        # If you need to use the database, you can get the database manager here
        db_manager_factory: UnifiedDBManagerFactory = self._system_app.get_component(
            ComponentType.UNIFIED_METADATA_DB_MANAGER_FACTORY,
            UnifiedDBManagerFactory,
            default_component=None,
        )
        if db_manager_factory is not None and db_manager_factory.create():
            init_db = db_manager_factory.create()
        else:
            init_db = self._db_url_or_db or db
            init_db = DatabaseManager.build_from(init_db, base=Model)

        if self._try_create_tables and self._not_create_table:
            try:
                init_db.create_all()
            except Exception as e:
                logger.warning(f"Failed to create tables: {e}")
            finally:
                self._not_create_table = False
        return init_db

    @classmethod
    def get_current_serve(cls, system_app: SystemApp) -> Optional["BaseServe"]:
        """Get the current serve component.

        None if the serve component is not exist.

        Args:
            system_app (SystemApp): The system app

        Returns:
            Optional[BaseServe]: The current serve component.
        """
        return cls.get_instance(system_app, default_component=None)

    @classmethod
    def call_on_current_serve(
        cls,
        system_app: SystemApp,
        func: Callable[["BaseServe"], Optional[Any]],
        default_value: Optional[Any] = None,
    ) -> Optional[Any]:
        """Call the function on the current serve component.

        Return default_value if the serve component is not exist or the function return None.

        Args:
            system_app (SystemApp): The system app
            func (Callable[[BaseServe], Any]): The function to call
            default_value (Optional[Any], optional): The default value. Defaults to None.

        Returns:
            Optional[Any]: The result of the function
        """
        serve = cls.get_current_serve(system_app)
        if not serve:
            return default_value
        result = func(serve)
        if not result:
            result = default_value
        return result
