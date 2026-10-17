"""Serve lifecycle for owner-scoped report persistence and APIs."""

from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.core import BaseServe

from .api.endpoints import _reset_endpoints, init_endpoints, router
from .config import (
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)
from .models.dao import ReportDao
from .service import ReportService


class ReportServe(BaseServe):
    """Mount report routes and bind their transactional service."""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = "/api/v1/reports",
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ) -> None:
        super().__init__(
            system_app,
            api_prefix or "/api/v1/reports",
            api_tags or [SERVE_APP_NAME_HUMP],
            db_url_or_db,
            try_create_tables,
        )
        self._config = config
        self._service: Optional[ReportService] = None
        self._db_manager: Optional[DatabaseManager] = None
        self._app_has_initiated: bool = False

    @property
    def service(self) -> Optional[ReportService]:
        return self._service

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
        self._app_has_initiated = True

    def on_init(self):
        """Import every entity so startup migration metadata can discover it."""
        from .models.models import (  # noqa: F401
            ReportArtifactDependencyEntity,
            ReportArtifactEntity,
            ReportEntity,
            ReportEvidenceEntity,
            ReportRunEntity,
        )

    def before_start(self):
        if self._db_manager is None:
            self._db_manager = self.create_or_get_db_manager()
        if self._service is None:
            self._service = ReportService(ReportDao(self._db_manager))
            init_endpoints(self._system_app, self._service)

    async def async_before_stop(self):
        _reset_endpoints()


__all__ = ["ReportServe"]
