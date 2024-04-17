import logging
from typing import List, Optional

from fastapi import HTTPException

from dbgpt._private.config import Config
from dbgpt._private.pydantic import model_to_dict
from dbgpt.component import ComponentType, SystemApp
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.datasource.db_conn_info import DBConfig
from dbgpt.datasource.manages.connect_config_db import (
    ConnectConfigDao,
    ConnectConfigEntity,
)
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.schema import DBType
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.executor_utils import ExecutorFactory

from ..api.schemas import DatasourceServeRequest, DatasourceServeResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig

logger = logging.getLogger(__name__)
CFG = Config()


class Service(
    BaseService[ConnectConfigEntity, DatasourceServeRequest, DatasourceServeResponse]
):
    """The service class for Flow"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: SystemApp,
        dao: Optional[ConnectConfigDao] = None,
    ):
        self._system_app = None
        self._dao: ConnectConfigDao = dao
        self._dag_manager: Optional[DAGManager] = None
        self._db_summary_client = None
        self._vector_connector = None

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or ConnectConfigDao()
        self._system_app = system_app

    def before_start(self):
        """Execute before the application starts"""
        from dbgpt.rag.summary.db_summary_client import DBSummaryClient

        self._db_summary_client = DBSummaryClient(self._system_app)

    def after_start(self):
        """Execute after the application starts"""

    @property
    def dao(
        self,
    ) -> BaseDao[ConnectConfigEntity, DatasourceServeRequest, DatasourceServeResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def create(self, request: DatasourceServeRequest) -> DatasourceServeResponse:
        """Create a new Datasource entity

        Args:
            request (DatasourceServeRequest): The request

        Returns:
            DatasourceServeResponse: The response
        """
        datasource = self._dao.get_by_names(request.db_name)
        if datasource:
            raise HTTPException(
                status_code=400,
                detail=f"datasource name:{request.db_name} already exists",
            )
        try:
            db_type = DBType.of_db_type(request.db_type)
            if not db_type:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported Db Type, {request.db_type}"
                )
            res = self._dao.create(request)

            # async embedding
            executor = self._system_app.get_component(
                ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
            ).create()  # type: ignore
            executor.submit(
                self._db_summary_client.db_summary_embedding,
                request.db_name,
                request.db_type,
            )
        except Exception as e:
            raise ValueError("Add db connect info error!" + str(e))
        return res

    def update(self, request: DatasourceServeRequest) -> DatasourceServeResponse:
        """Create a new Datasource entity

        Args:
            request (DatasourceServeRequest): The request

        Returns:
            DatasourceServeResponse: The response
        """
        datasources = self._dao.get_by_names(request.db_name)
        if datasources is None:
            raise HTTPException(
                status_code=400,
                detail=f"there is no datasource name:{request.db_name} exists",
            )
        db_config = DBConfig(**model_to_dict(request))
        if CFG.local_db_manager.edit_db(db_config):
            return DatasourceServeResponse(**model_to_dict(db_config))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"update datasource name:{request.db_name} failed",
            )

    def get(self, datasource_id: str) -> Optional[DatasourceServeResponse]:
        """Get a Flow entity

        Args:
            request (DatasourceServeRequest): The request

        Returns:
            DatasourceServeResponse: The response
        """
        return self._dao.get_one({"id": datasource_id})

    def delete(self, datasource_id: str) -> Optional[DatasourceServeResponse]:
        """Delete a Flow entity

        Args:
            datasource_id (str): The datasource_id

        Returns:
            DatasourceServeResponse: The data after deletion
        """
        db_config = self._dao.get_one({"id": datasource_id})
        vector_name = db_config.db_name + "_profile"
        vector_store_config = VectorStoreConfig(name=vector_name)
        self._vector_connector = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE,
            vector_store_config=vector_store_config,
        )
        self._vector_connector.delete_vector_name(vector_name)
        if db_config:
            self._dao.delete({"id": datasource_id})
        return db_config

    def list(self) -> List[DatasourceServeResponse]:
        """List the Flow entities.

        Returns:
            List[DatasourceServeResponse]: The list of responses
        """

        db_list = CFG.local_db_manager.get_db_list()
        return [DatasourceServeResponse(**db) for db in db_list]
