import logging
import os
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.core import BaseServe

from .api.endpoints import init_endpoints, router
from .api.git_repo_endpoints import init_git_repo_endpoints
from .api.git_repo_endpoints import router as git_repo_router
from .api.search_endpoints import init_search_endpoints
from .api.search_endpoints import router as search_router
from .api.wiki_endpoints import init_wiki_endpoints
from .api.wiki_endpoints import router as wiki_router
from .config import (
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)
from .knowledge_source.api import init_knowledge_source_endpoints
from .knowledge_source.api import router as knowledge_source_router

logger = logging.getLogger(__name__)


class Serve(BaseServe):
    """Serve component for DB-GPT"""

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: Optional[ServeConfig] = None,
        api_prefix: Optional[str] = "/api/v2/serve/knowledge",
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
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._api_tags
        )
        # Register git repo and search tool endpoints
        self._system_app.app.include_router(
            git_repo_router, prefix=self._api_prefix, tags=self._api_tags
        )
        self._system_app.app.include_router(
            search_router, prefix=self._api_prefix, tags=self._api_tags
        )
        # Register wiki (LLM-Wiki) endpoints
        self._system_app.app.include_router(
            wiki_router, prefix=self._api_prefix, tags=self._api_tags
        )
        # Register knowledge source endpoints
        self._system_app.app.include_router(
            knowledge_source_router, prefix=self._api_prefix, tags=self._api_tags
        )
        self._config = self._config or ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        init_endpoints(self._system_app, self._config)
        init_git_repo_endpoints(self._system_app, self._config)
        init_search_endpoints(self._system_app, self._config)
        init_wiki_endpoints(self._system_app, self._config)
        init_knowledge_source_endpoints(self._system_app, self._config)
        self._app_has_initiated = True

    def on_init(self):
        """Called when init the application.

        You can do some initialization here. You can't get other components here
        because they may be not initialized yet
        """
        # import your own module here to ensure the module is loaded before the
        # application starts
        from .knowledge_source.models import (  # noqa: F401
            KnowledgeSourceEntity,
            KnowledgeSourceKeyEntity,
            KnowledgeSourceSyncLogEntity,
        )
        from .models.code_graph_db import (  # noqa: F401
            CodeGraphEdgeEntity,
            CodeGraphMetaEntity,
            CodeGraphVertexEntity,
        )
        from .models.models import KnowledgeSpaceEntity as _  # noqa: F401
        from .models.wiki_db import (  # noqa: F401
            KnowledgeWikiPageEntity,
            KnowledgeWikiPageRevisionEntity,
            KnowledgeWikiTaskEntity,
        )

    def before_start(self):
        """Called before the start of the application."""
        # TODO: Your code here
        self._db_manager = self.create_or_get_db_manager()

    def after_start(self):
        """Start the wiki task scheduler once the app is fully bootstrapped."""
        self._start_wiki_scheduler()

    def _start_wiki_scheduler(self):
        from .service.wiki.pipeline import WikiIngestPipeline
        from .service.wiki.task_scheduler import WikiTaskScheduler

        system_app = self._system_app

        async def _handle(cfg, payload, task_type: str):
            from .models.models import KnowledgeSpaceDao

            spaces = KnowledgeSpaceDao().get_knowledge_space_by_ids([cfg.space_id])
            if not spaces:
                return
            pipeline = WikiIngestPipeline(system_app, spaces[0], cfg)
            if task_type == "wiki:ingest":
                await pipeline.run_ingest(payload.get("document_ids") or [])
            elif task_type == "wiki:finalize":
                await pipeline.run_finalize()
            elif task_type == "wiki:reconcile":
                deleted_id = payload.get("deleted_document_id")
                if deleted_id:
                    await pipeline.run_reconcile(int(deleted_id))

        scheduler = WikiTaskScheduler(system_app)

        async def _ingest(cfg, payload):
            await _handle(cfg, payload, "wiki:ingest")

        async def _finalize(cfg, payload):
            await _handle(cfg, payload, "wiki:finalize")

        async def _reconcile(cfg, payload):
            await _handle(cfg, payload, "wiki:reconcile")

        scheduler.register_handler("wiki:ingest", _ingest)
        scheduler.register_handler("wiki:finalize", _finalize)
        scheduler.register_handler("wiki:reconcile", _reconcile)
        scheduler.start()
        if self._system_app.app is not None:
            self._system_app.app.add_event_handler("shutdown", scheduler.stop)

        # knowledge source connectors + due-binding scheduler
        try:
            from dbgpt_ext.knowledge_source.registry import (
                ensure_source_connectors_loaded,
            )
            from dbgpt_serve.rag.knowledge_source.scheduler import (
                KnowledgeSourceScheduler,
            )
            from dbgpt_serve.rag.knowledge_source.service import (
                KnowledgeSourceService,
            )

            ensure_source_connectors_loaded(
                _apply_knowledge_source_settings(self._system_app)
            )
            ks_sdk = KnowledgeSourceScheduler(KnowledgeSourceService(self._system_app))
            ks_sdk.start()
            if self._system_app.app is not None:
                self._system_app.app.add_event_handler("shutdown", ks_sdk.stop)
        except Exception as exc:  # noqa: BLE001 - datasources must not kill boot
            logger.warning(f"knowledge source framework disabled: {exc}")


def _apply_knowledge_source_settings(system_app) -> list:
    """Load [rag.knowledge_source] settings from the app config.

    extra_connector_modules → returned for the loader; TLS knobs (ca_bundle,
    insecure_tls) and nothing else are mirrored into ``os.environ`` via
    setdefault so the shared HTTP client honors whichever channel (toml or
    env) the operator chose — env wins.
    """
    modules: list = []
    try:
        rag_cfg = system_app.config.configs.get("app_config").rag
        ks = getattr(rag_cfg, "knowledge_source", None)
        modules = list(getattr(ks, "extra_connector_modules", None) or [])
        mapping = {
            "ca_bundle": "DB_GPT_KS_CA_BUNDLE",
            "insecure_tls": "DB_GPT_KS_INSECURE",
        }
        for attr, env_key in mapping.items():
            value = getattr(ks, attr, None)
            if value in (None, ""):
                continue
            if isinstance(value, bool):
                value = "1" if value else "0"
            os.environ.setdefault(env_key, str(value))
    except Exception:  # noqa: BLE001 - config shape differences must not kill boot
        pass
    return modules
