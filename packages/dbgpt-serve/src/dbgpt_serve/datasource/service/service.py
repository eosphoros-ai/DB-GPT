import logging
from typing import List, Optional, Union

from dbgpt._private.config import Config
from dbgpt._private.pydantic import model_to_dict
from dbgpt.component import ComponentType, SystemApp
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.util.executor_utils import ExecutorFactory
from dbgpt_ext.datasource.schema import DBType
from fastapi import HTTPException

from dbgpt_serve.core import BaseService, ResourceTypes
from dbgpt_serve.datasource.manages import ConnectorManager
from dbgpt_serve.datasource.manages.connect_config_db import (
    ConnectConfigDao,
    ConnectConfigEntity,
)
from dbgpt_serve.datasource.manages.db_conn_info import DBConfig
from dbgpt_serve.rag.connector import VectorStoreConnector

from ..api.schemas import (
    DatasourceCreateRequest,
    DatasourceServeRequest,
    DatasourceServeResponse,
)
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
        super().init_app(system_app)

        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or ConnectConfigDao()
        self._system_app = system_app

    def before_start(self):
        """Execute before the application starts"""
        from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient

        super().before_start()
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

    @property
    def datasource_manager(self) -> ConnectorManager:
        if not self._system_app:
            raise ValueError("SYSTEM_APP is not set")
        return ConnectorManager.get_instance(self._system_app)

    def create(
        self, request: Union[DatasourceCreateRequest, DatasourceServeRequest]
    ) -> DatasourceServeResponse:
        """Create a new Datasource entity

        Args:
            request (Union[DatasourceCreateRequest, DatasourceServeRequest]): The
                request to create a new Datasource entity. DatasourceServeRequest is
                deprecated.

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
        if self.datasource_manager.edit_db(db_config):
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

        db_list = self.datasource_manager.get_db_list()
        return [DatasourceServeResponse(**db) for db in db_list]

    def datasource_types(self) -> ResourceTypes:
        """List the datasource types.

        Returns:
            List[str]: The list of datasource types
        """
        return self.datasource_manager.get_supported_types()

    def test_connection(self, request: DatasourceCreateRequest) -> bool:
        """Test the connection of the datasource.

        Args:
            request (DatasourceServeRequest): The request

        Returns:
            bool: The test result
        """
        return self.datasource_manager.test_connection(request)
