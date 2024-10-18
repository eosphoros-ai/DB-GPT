import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.serve.core import BaseServe
from dbgpt.storage.metadata import DatabaseManager

from .api.endpoints import init_endpoints, router
from .config import APP_NAME, SERVE_APP_NAME, SERVE_APP_NAME_HUMP

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
        api_prefix: Optional[List[str]] = None,
        api_tags: Optional[List[str]] = None,
        db_url_or_db: Union[str, URL, DatabaseManager] = None,
        try_create_tables: Optional[bool] = False,
    ):
        if api_prefix is None:
            api_prefix = [f"/api/v1/{APP_NAME}", f"/api/v2/serve/{APP_NAME}"]
        if api_tags is None:
            api_tags = [SERVE_APP_NAME_HUMP]
        super().__init__(
            system_app, api_prefix, api_tags, db_url_or_db, try_create_tables
        )

    def init_app(self, system_app: SystemApp):
        if self._app_has_initiated:
            return
        self._system_app = system_app
        for prefix in self._api_prefix:
            self._system_app.app.include_router(
                router, prefix=prefix, tags=self._api_tags
            )
        init_endpoints(self._system_app)
        self._app_has_initiated = True

    def on_init(self):
        """Called before the start of the application.

        You can do some initialization here.
        """
        # import your own module here to ensure the module is loaded before the application starts

    def before_start(self):
        """Called before the start of the application.

        You can do some initialization here.
        """
        # import your own module here to ensure the module is loaded before the application starts
