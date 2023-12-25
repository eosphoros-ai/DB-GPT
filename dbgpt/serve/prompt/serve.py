import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core import PromptManager

from ...storage.metadata import DatabaseManager
from .api.endpoints import init_endpoints, router
from .config import (
    APP_NAME,
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)
from .models.prompt_template_adapter import PromptTemplateAdapter

logger = logging.getLogger(__name__)


class Serve(BaseComponent):
    """Serve component

    Examples:

        Register the serve component to the system app

        .. code-block:: python

            from fastapi import FastAPI
            from dbgpt import SystemApp
            from dbgpt.core import PromptTemplate
            from dbgpt.serve.prompt.serve import Serve, SERVE_APP_NAME

            app = FastAPI()
            system_app = SystemApp(app)
            system_app.register(Serve, api_prefix="/api/v1/prompt")
            # Run before start hook
            system_app.before_start()

            prompt_serve = system_app.get_component(SERVE_APP_NAME, Serve)

            # Get the prompt manager
            prompt_manager = prompt_serve.prompt_manager
            prompt_manager.save(
                PromptTemplate(template="Hello {name}", input_variables=["name"]),
                prompt_name="prompt_name",
            )

        With your database url

        .. code-block:: python

            from fastapi import FastAPI
            from dbgpt import SystemApp
            from dbgpt.core import PromptTemplate
            from dbgpt.serve.prompt.serve import Serve, SERVE_APP_NAME

            app = FastAPI()
            system_app = SystemApp(app)
            system_app.register(Serve, api_prefix="/api/v1/prompt", db_url_or_db="sqlite:///:memory:", try_create_tables=True)
            # Run before start hook
            system_app.before_start()

            prompt_serve = system_app.get_component(SERVE_APP_NAME, Serve)

            # Get the prompt manager
            prompt_manager = prompt_serve.prompt_manager
            prompt_manager.save(
                PromptTemplate(template="Hello {name}", input_variables=["name"]),
                prompt_name="prompt_name",
            )

    """

    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        api_prefix: Optional[str] = f"/api/v1/serve/{APP_NAME}",
        tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if tags is None:
            tags = [SERVE_APP_NAME_HUMP]
        self._system_app = None
        self._api_prefix = api_prefix
        self._tags = tags
        self._prompt_manager = None
        self._db_url_or_db = db_url_or_db
        self._try_create_tables = try_create_tables

    def init_app(self, system_app: SystemApp):
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._tags
        )
        init_endpoints(self._system_app)

    @property
    def prompt_manager(self) -> PromptManager:
        """Get the prompt manager of the serve app with db storage"""
        return self._prompt_manager

    def before_start(self):
        """Called before the start of the application.

        You can do some initialization here.
        """
        # import your own module here to ensure the module is loaded before the application starts
        from dbgpt.core.interface.prompt import PromptManager
        from dbgpt.storage.metadata import Model, db
        from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
        from dbgpt.util.serialization.json_serialization import JsonSerializer

        from .models.models import ServeEntity

        init_db = self._db_url_or_db or db
        init_db = DatabaseManager.build_from(init_db, base=Model)
        if self._try_create_tables:
            try:
                init_db.create_all()
            except Exception as e:
                logger.warning(f"Failed to create tables: {e}")
        storage_adapter = PromptTemplateAdapter()
        serializer = JsonSerializer()
        storage = SQLAlchemyStorage(
            init_db,
            ServeEntity,
            storage_adapter,
            serializer,
        )
        self._prompt_manager = PromptManager(storage)
