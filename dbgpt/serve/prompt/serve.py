from typing import List, Optional
from dbgpt.component import BaseComponent, SystemApp

from .api.endpoints import router, init_endpoints
from .config import (
    SERVE_APP_NAME,
    SERVE_APP_NAME_HUMP,
    APP_NAME,
    SERVE_CONFIG_KEY_PREFIX,
    ServeConfig,
)


class Serve(BaseComponent):
    name = SERVE_APP_NAME

    def __init__(
        self,
        system_app: SystemApp,
        api_prefix: Optional[str] = f"/api/v1/serve/{APP_NAME}",
        tags: Optional[List[str]] = None,
    ):
        if tags is None:
            tags = [SERVE_APP_NAME_HUMP]
        self._system_app = None
        self._api_prefix = api_prefix
        self._tags = tags

    def init_app(self, system_app: SystemApp):
        self._system_app = system_app
        self._system_app.app.include_router(
            router, prefix=self._api_prefix, tags=self._tags
        )
        init_endpoints(self._system_app)

    def before_start(self):
        """Called before the start of the application.

        You can do some initialization here.
        """
        # import your own module here to ensure the module is loaded before the application starts
        from .models.models import ServeEntity
