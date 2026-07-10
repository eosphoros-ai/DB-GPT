"""ConnectorServe - registers connector API routes and manages connector lifecycle."""

import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.core import BaseServe

from .api.endpoints import init_endpoints, router
from .config import (
    APP_NAME,
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)

logger = logging.getLogger(__name__)


class ConnectorServe(BaseServe):
    """Serve component for the Connector service."""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = f"/api/v2/serve/{APP_NAME}s",
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if api_tags is None:
            api_tags = [SERVE_APP_NAME_HUMP]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )
        self._config = config

    def init_app(self, system_app: SystemApp):
        if self._app_has_initiated:
            return
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )

        config = self._config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )

        init_endpoints(self._system_app, config)
        self._app_has_initiated = True

    def on_init(self):
        from .models.models import ConnectorInstanceEntity as _  # noqa: F401

    def before_start(self):
        self.create_or_get_db_manager()
