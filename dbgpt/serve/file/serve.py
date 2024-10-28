import logging
from typing import List, Optional, Union

from sqlalchemy import URL

from dbgpt.component import SystemApp
from dbgpt.core.interface.file import FileStorageClient
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
        api_prefix: Optional[str] = f"/api/v2/serve/{APP_NAME}",
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

        self._db_manager: Optional[DatabaseManager] = None
        self._file_storage_client: Optional[FileStorageClient] = None
        self._serve_config: Optional[ServeConfig] = None

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
        from dbgpt.core.interface.file import (
            FileStorageSystem,
            SimpleDistributedStorage,
        )
        from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
        from dbgpt.util.serialization.json_serialization import JsonSerializer

        from .models.file_adapter import FileMetadataAdapter
        from .models.models import ServeEntity

        self._serve_config = ServeConfig.from_app_config(
            self._system_app.config, SERVE_CONFIG_KEY_PREFIX
        )

        self._db_manager = self.create_or_get_db_manager()
        serializer = JsonSerializer()
        storage = SQLAlchemyStorage(
            self._db_manager,
            ServeEntity,
            FileMetadataAdapter(),
            serializer,
        )
        simple_distributed_storage = SimpleDistributedStorage(
            node_address=self._serve_config.get_node_address(),
            local_storage_path=self._serve_config.get_local_storage_path(),
            save_chunk_size=self._serve_config.file_server_save_chunk_size,
            transfer_chunk_size=self._serve_config.file_server_transfer_chunk_size,
            transfer_timeout=self._serve_config.file_server_transfer_timeout,
        )
        storage_backends = {
            simple_distributed_storage.storage_type: simple_distributed_storage,
        }
        fs = FileStorageSystem(
            storage_backends,
            metadata_storage=storage,
            check_hash=self._serve_config.check_hash,
        )
        self._file_storage_client = FileStorageClient(
            system_app=self._system_app, storage_system=fs
        )

    @property
    def file_storage_client(self) -> FileStorageClient:
        """Returns the file storage client."""
        if not self._file_storage_client:
            raise ValueError("File storage client is not initialized")
        return self._file_storage_client
