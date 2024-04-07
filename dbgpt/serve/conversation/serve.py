import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.core import StorageInterface
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
from .service.service import Service

logger = logging.getLogger(__name__)


class Serve(BaseServe):
    """Serve component for DB-GPT

    Message DB-GPT conversation history and provide API for other components to access.

    TODO: Move some Http API in app to this component.
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
        self._db_manager: Optional[DatabaseManager] = None
        self._conv_storage = None
        self._message_storage = None

    @property
    def conv_storage(self) -> StorageInterface:
        return self._conv_storage

    @property
    def message_storage(self) -> StorageInterface:
        return self._message_storage

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
        # Load DB Model
        from dbgpt.storage.chat_history.chat_history_db import (
            ChatHistoryEntity,
            ChatHistoryMessageEntity,
        )

    def before_start(self):
        """Called before the start of the application."""
        # TODO: Your code here
        from dbgpt.storage.chat_history.chat_history_db import (
            ChatHistoryEntity,
            ChatHistoryMessageEntity,
        )
        from dbgpt.storage.chat_history.storage_adapter import (
            DBMessageStorageItemAdapter,
            DBStorageConversationItemAdapter,
        )
        from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
        from dbgpt.util.serialization.json_serialization import JsonSerializer

        from .operators import DefaultServePreChatHistoryLoadOperator

        self._db_manager = self.create_or_get_db_manager()

        self._conv_storage = SQLAlchemyStorage(
            self._db_manager,
            ChatHistoryEntity,
            DBStorageConversationItemAdapter(),
            JsonSerializer(),
        )
        self._message_storage = SQLAlchemyStorage(
            self._db_manager,
            ChatHistoryMessageEntity,
            DBMessageStorageItemAdapter(),
            JsonSerializer(),
        )
