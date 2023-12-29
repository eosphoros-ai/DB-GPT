import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.core import PromptManager

from dbgpt.storage.metadata import DatabaseManager
from dbgpt.serve.core import BaseServe
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


class Serve(BaseServe):
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
            system_app.on_init()
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
            system_app.register(
                Serve,
                api_prefix="/api/v1/prompt",
                db_url_or_db="sqlite:///:memory:",
                try_create_tables=True,
            )
            system_app.on_init()
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
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if api_tags is None:
            api_tags = [SERVE_APP_NAME_HUMP]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )
        self._prompt_manager = None
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

    @property
    def prompt_manager(self) -> PromptManager:
        """Get the prompt manager of the serve app with db storage"""
        return self._prompt_manager

    def on_init(self):
        """Called before the start of the application.

        You can do some initialization here.
        """
        # import your own module here to ensure the module is loaded before the application starts
        from .models.models import ServeEntity

    def before_start(self):
        """Called before the start of the application.

        You can do some initialization here.
        """
        # import your own module here to ensure the module is loaded before the application starts
        from dbgpt.core.interface.prompt import PromptManager
        from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
        from dbgpt.util.serialization.json_serialization import JsonSerializer

        from .models.models import ServeEntity

        self._db_manager = self.create_or_get_db_manager()
        storage_adapter = PromptTemplateAdapter()
        serializer = JsonSerializer()
        storage = SQLAlchemyStorage(
            self._db_manager,
            ServeEntity,
            storage_adapter,
            serializer,
        )
        self._prompt_manager = PromptManager(storage)
