import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.core import InMemoryStorage, StorageInterface
from dbgpt.storage.metadata import DatabaseManager
from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
from dbgpt.util.serialization.json_serialization import JsonSerializer
from dbgpt_serve.core import BaseServe

from .api.endpoints import init_endpoints, router
from .config import (  # noqa: F401
    APP_NAME,
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)

logger = logging.getLogger(__name__)


class Serve(BaseServe):
    """Serve component for DB-GPT"""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = None,
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if not api_prefix:
            api_prefix = ["/api/v1/worker", f"/api/v2/serve/{APP_NAME}"]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )
        self._db_manager: Optional[DatabaseManager] = None
        self._config = config
        self._model_storage: Optional[StorageInterface] = None

    def init_app(self, system_app: SystemApp):
        if self._app_has_initiated:
            return
        self._system_app = system_app
        for prefix in self._api_prefix:
            self._system_app.app.include_router(
                router, prefix=prefix, tags=self._api_tags
            )
        self._config = self._config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        init_endpoints(self._system_app, self._config)
        self._app_has_initiated = True

    def on_init(self):
        """Called when init the application.

        You can do some initialization here. You can't get other components here
        because they may be not initialized yet
        """
        # import your own module here to ensure the module is loaded before the
        # application starts
        from .models.models import ServeEntity as _  # noqa: F401

    def after_init(self):
        """Called before the start of the application."""
        from .models.model_adapter import ModelStorageAdapter
        from .models.models import ServeEntity

        self._db_manager = self.create_or_get_db_manager()
        serializer = JsonSerializer()
        if self.config.model_storage == "memory":
            self._model_storage = InMemoryStorage(serializer)
        elif self.config.model_storage == "database" or not self.config.model_storage:
            self._model_storage = SQLAlchemyStorage(
                self._db_manager,
                ServeEntity,
                ModelStorageAdapter(),
                serializer,
            )
        else:
            raise ValueError(f"Invalid model storage type: {self.config.model_storage}")

    @property
    def model_storage(self) -> StorageInterface:
        """Get the model storage of the serve app with db storage"""
        if not self._model_storage:
            raise ValueError("Model storage is not initialized")
        return self._model_storage

    @property
    def config(self) -> ServeConfig:
        """Get the config"""
        if not self._config:
            raise ValueError("Config is not initialized")
        return self._config
