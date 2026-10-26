"""SessionFileServe - mount the session file API and hold the registry.

Lifecycle (mirrors ``scheduled_task/serve.py``):
    init_app          - mount the router under /api/v1/agent/files, build the
                        registry (storage seam, DAO, inspector, config, work
                        root) and bind it to the endpoints module
    on_init           - import the Entity class to register SQLAlchemy metadata
    after_init        - refresh financial capabilities after application migration
    before_start      - create/get the database manager and bind shared storage
    async_before_stop - close the registry and unbind the endpoints module so
                        storage-backed endpoints fail closed again
"""

import logging
from pathlib import Path
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.core.interface.file import FileStorageClient
from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_serve.core import BaseServe

from .api.endpoints import _reset_endpoints, init_endpoints, router
from .config import (
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)
from .inspector import SessionFileInspector
from .models.dao import SessionFileDao
from .registry import SessionFileRegistry

logger = logging.getLogger(__name__)

_WORK_ROOT_CONFIG_KEY = f"{SERVE_CONFIG_KEY_PREFIX}work_root"


def default_work_root() -> Path:
    """Persistent local work root for materialized session file staging.

    Never the system temp directory: the root persists across restarts so
    staged artifacts and the future GC can rely on a stable location.
    """
    return Path.home() / ".cache" / "dbgpt" / "session_files" / "work"


class SessionFileServe(BaseServe):
    """Serve component mounting the owner-aware session file API."""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = "/api/v1/agent/files",
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
        storage_client: Optional[FileStorageClient] = None,
        inspector: Optional[SessionFileInspector] = None,
        registry: Optional[SessionFileRegistry] = None,
        work_root: Optional[Union[str, Path]] = None,
    ):
        if api_tags is None:
            api_tags = [SERVE_APP_NAME_HUMP]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )
        self._serve_config = config
        self._storage_client = storage_client
        self._inspector = inspector
        self._registry = registry
        self._work_root = Path(work_root) if work_root is not None else None
        self._db_manager: Optional[DatabaseManager] = None
        self._financial_analysis = None
        self._uses_fallback_storage = False

    @property
    def registry(self) -> Optional[SessionFileRegistry]:
        """Return the orchestrating registry bound during ``init_app``."""
        return self._registry

    @property
    def financial_analysis(self):
        """Shared report persistence and validation for API and agent tools."""
        return self._financial_analysis

    def init_app(self, system_app: SystemApp):
        """Mount the router and bind the registry to the endpoints module."""
        if self._app_has_initiated:
            return
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )
        self._serve_config = self._serve_config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        if self._registry is None:
            self._registry = SessionFileRegistry(
                storage_client=self._resolve_storage_client(system_app),
                dao=self._build_dao(),
                inspector=self._inspector or SessionFileInspector(),
                config=self._serve_config,
                work_root=self._resolve_work_root(system_app),
            )
        init_endpoints(system_app, self._registry, self._serve_config)
        from dbgpt_serve.financial_analysis.api import make_router
        from dbgpt_serve.financial_analysis.service import FinancialAnalysisService

        self._financial_analysis = FinancialAnalysisService(self._registry)
        system_app.app.include_router(
            make_router(self._financial_analysis),
            prefix="/api/v1/financial-analysis",
            tags=["FinancialAnalysis"],
        )
        self._app_has_initiated = True

    def on_init(self):
        """Import the Entity class to register SQLAlchemy metadata."""
        from dbgpt_serve.financial_analysis.models import (
            FinancialReportRevisionEntity,  # noqa: F401
            FinancialRunDocumentEntity,  # noqa: F401
            FinancialRunEntity,  # noqa: F401
        )

        from .models.models import SessionFileEntity  # noqa: F401

    def after_init(self):
        """Observe schema upgrades performed after component registration."""
        if self._financial_analysis is not None:
            self._financial_analysis.refresh_schema()

    def before_start(self):
        """Initialize metadata and bind storage registered during after_init."""
        self._db_manager = self.create_or_get_db_manager()
        # FileServe registers its persistent client in after_init, later than
        # this component's init_app. Replace only our temporary fallback before
        # accepting requests; explicit clients/registries remain untouched.
        if self._uses_fallback_storage and self._registry is not None:
            client = FileStorageClient.get_instance(
                self._system_app, default_component=None
            )
            if client is not None:
                self._registry.bind_storage_client(client)
                self._uses_fallback_storage = False

    async def async_before_stop(self):
        """Close the registry and unbind the endpoints module."""
        if self._financial_analysis is not None:
            import asyncio

            try:
                await asyncio.to_thread(self._financial_analysis.close)
            except Exception:
                logger.exception("Failed to close financial analysis service")
        if self._registry is not None:
            try:
                self._registry.close()
            except Exception:
                logger.exception("Failed to close session file registry")
        _reset_endpoints()
        logger.info("Session file endpoints unbound; serve stopped.")

    async def async_after_start(self):
        """Bind model work to the serving event loop after components initialize."""
        import asyncio
        import os

        from dbgpt_serve.financial_analysis.analysis import QwenAnalyzer
        from dbgpt_serve.financial_analysis.questions import QwenQuestionAnswerer

        if self._financial_analysis is not None:
            self._financial_analysis.analyzer = QwenAnalyzer(
                self._system_app,
                asyncio.get_running_loop(),
                model=os.getenv("DBGPT_FINANCIAL_MODEL", "qwen-plus"),
            )
            self._financial_analysis.answerer = QwenQuestionAnswerer(
                self._system_app,
                asyncio.get_running_loop(),
                model=os.getenv("DBGPT_FINANCIAL_MODEL", "qwen-plus"),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_dao(self) -> SessionFileDao:
        if self._db_url_or_db is not None:
            manager = DatabaseManager.build_from(self._db_url_or_db, base=Model)
            return SessionFileDao(manager)
        return SessionFileDao()

    def _resolve_work_root(self, system_app: SystemApp) -> Path:
        if self._work_root is not None:
            return self._work_root
        raw = None
        try:
            raw = system_app.config.get(_WORK_ROOT_CONFIG_KEY)
        except Exception:
            logger.debug("No work_root configured in app config; using default")
        if raw:
            return Path(raw)
        return default_work_root()

    def _resolve_storage_client(self, system_app: SystemApp):
        """Prefer the app-shared FileStorageClient; create a local fallback."""
        if self._storage_client is not None:
            return self._storage_client
        client = FileStorageClient.get_instance(system_app, default_component=None)
        if client is not None:
            return client
        logger.info(
            "No shared FileStorageClient registered; session file serve "
            "creates a default local storage client."
        )
        self._uses_fallback_storage = True
        return FileStorageClient()
