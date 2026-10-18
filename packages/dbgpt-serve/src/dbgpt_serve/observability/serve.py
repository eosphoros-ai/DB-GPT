"""Serve component for the observability module.

A pure proxy: it mounts the HTTP router and delegates everything to an
:class:`ObservabilityProvider`. The provider owns its own storage (default SQLite
file or ZizkaDB), so this serve does NOT touch the main metadata DB.
"""

import logging
from typing import List, Optional

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.core import BaseServe

from .api.endpoints import init_endpoints, router
from .config import (
    APP_NAME,
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,  # noqa: F401
    ServeConfig,
)

logger = logging.getLogger(__name__)


class Serve(BaseServe):
    """Serve component for DB-GPT Agent observability."""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = f"/api/v1/serve/{APP_NAME}",
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Optional[URL | str | DatabaseManager] = None,
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
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )
        self._config = self._config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        init_endpoints(self._system_app, self._config)
        self._app_has_initiated = True

    def on_init(self):
        """Called on application init; nothing to load for a proxy serve."""

    def before_start(self):
        """Called before start. No DB tables needed (provider owns its storage)."""
        # Create/get a db manager only to satisfy BaseServe expectations; the
        # observability provider does not use the main metadata DB.
        self._db_manager = self.create_or_get_db_manager()
