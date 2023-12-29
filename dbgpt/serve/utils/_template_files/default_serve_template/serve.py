import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.serve.core import BaseServe
from dbgpt.storage.metadata import DatabaseManager

from .api.endpoints import init_endpoints, router
from .config import (
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
        api_prefix: Optional[str] = f"/api/v1/serve/{APP_NAME}",
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

    def init_app(self, system_app: SystemApp):
        if self._app_has_initiated:
            return
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )
        init_endpoints(self._system_app)
        self._app_has_initiated = True

    def on_init(self):
        """Called when init the application.

        You can do some initialization here. You can't get other components here because they may be not initialized yet
        """
        # import your own module here to ensure the module is loaded before the application starts
        from .models.models import ServeEntity

    def before_start(self):
        """Called before the start of the application."""
        # TODO: Your code here
        self._db_manager = self.create_or_get_db_manager()
