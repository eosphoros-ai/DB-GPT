import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.core import BaseServe

from .api.endpoints import init_endpoints, router
from .config import (
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    SERVE_SERVICE_COMPONENT_NAME,
    ServeConfig,
)
from .service.service import Service

logger = logging.getLogger(__name__)


class Serve(BaseServe):
    """Serve component for the plugins (expert suite) module."""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = "/api/v1/suites",
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if api_tags is None:
            api_tags = [SERVE_APP_NAME_HUMP]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )
        self._db_manager: Optional[DatabaseManager] = None
        self._config = config

    def init_app(self, system_app: SystemApp):
        if self._app_has_initiated:
            return
        from .api.creation import router as creation_router

        self._system_app = system_app
        self._system_app.app.include_router(
            creation_router, prefix="/api/v1", tags=self._api_tags
        )
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )
        self._config = self._config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        init_endpoints(self._system_app, self._config)
        self._app_has_initiated = True

    def on_init(self):
        # Import models so the tables are registered on Model.metadata.
        from .models.models import SuiteEntity, SuiteEventEntity  # noqa: F401

    def before_start(self):
        self._db_manager = self.create_or_get_db_manager()

    def after_start(self):
        """Sync official suite packages from disk into the registry (fail-soft)."""
        try:
            service = self._system_app.get_component(
                SERVE_SERVICE_COMPONENT_NAME, Service
            )
            service.sync_official_on_start()
        except Exception as exc:  # noqa: BLE001 - startup must not crash on bad packs
            logger.warning("official suite sync skipped: %s", exc)
