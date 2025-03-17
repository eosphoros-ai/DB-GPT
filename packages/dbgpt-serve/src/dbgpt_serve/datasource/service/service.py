import json
import logging
from typing import List, Optional, Union

from fastapi import HTTPException

from dbgpt._private.config import Config
from dbgpt._private.pydantic import model_to_dict
from dbgpt.component import ComponentType, SystemApp
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.storage.metadata import BaseDao
from dbgpt.util.executor_utils import ExecutorFactory
from dbgpt_ext.datasource.schema import DBType
from dbgpt_serve.core import BaseService, ResourceTypes
from dbgpt_serve.datasource.manages import ConnectorManager
from dbgpt_serve.datasource.manages.connect_config_db import (
    ConnectConfigDao,
    ConnectConfigEntity,
)

from ...rag.storage_manager import StorageManager
from ..api.schemas import (
    DatasourceCreateRequest,
    DatasourceQueryResponse,
    DatasourceServeRequest,
    DatasourceServeResponse,
)
from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig

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
        config: ServeConfig,
        dao: Optional[ConnectConfigDao] = None,
    ):
        self._system_app = system_app
        self._dao: ConnectConfigDao = dao
        self._dag_manager: Optional[DAGManager] = None
        self._db_summary_client = None
        self._serve_config = config

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        super().init_app(system_app)

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

    @property
    def storage_manager(self) -> StorageManager:
        if not self._system_app:
            raise ValueError("SYSTEM_APP is not set")
        return StorageManager.get_instance(self._system_app)

    def create(
        self, request: Union[DatasourceCreateRequest, DatasourceServeRequest]
    ) -> DatasourceQueryResponse:
        """Create a new Datasource entity

        Args:
            request (Union[DatasourceCreateRequest, DatasourceServeRequest]): The
                request to create a new Datasource entity. DatasourceServeRequest is
                deprecated.

        Returns:
            DatasourceQueryResponse: The response
        """
        str_db_type = (
            request.type
            if isinstance(request, DatasourceCreateRequest)
            else request.db_type
        )
        desc = ""
        if isinstance(request, DatasourceCreateRequest):
            connector_params: BaseDatasourceParameters = (
                self.datasource_manager._create_parameters(request)
            )
            persisted_state = connector_params.persisted_state()
            desc = request.description
        else:
            persisted_state = model_to_dict(request)
            desc = request.comment
        if "ext_config" in persisted_state and isinstance(
            persisted_state["ext_config"], dict
        ):
            persisted_state["ext_config"] = json.dumps(
                persisted_state["ext_config"], ensure_ascii=False
            )
        persisted_state["comment"] = desc
        db_name = persisted_state.get("db_name")
        datasource = self._dao.get_by_names(db_name)
        if datasource:
            raise HTTPException(
                status_code=400,
                detail=f"datasource name:{db_name} already exists",
            )
        try:
            db_type = DBType.of_db_type(str_db_type)
            if not db_type:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported Db Type, {str_db_type}"
                )

            res = self._dao.create(persisted_state)

            # async embedding
            executor = self._system_app.get_component(
                ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
            ).create()  # type: ignore
            executor.submit(
                self._db_summary_client.db_summary_embedding,
                db_name,
                str_db_type,
            )
        except Exception as e:
            raise ValueError("Add db connect info error!" + str(e))
        return self._to_query_response(res)

    def update(
        self, request: Union[DatasourceCreateRequest, DatasourceServeRequest]
    ) -> DatasourceQueryResponse:
        """Create a new Datasource entity

        Args:
            request (Union[DatasourceCreateRequest, DatasourceServeRequest]): The
                request to create a new Datasource entity. DatasourceServeRequest is
                deprecated.

        Returns:
            DatasourceQueryResponse: The response
        """
        str_db_type = (
            request.type
            if isinstance(request, DatasourceCreateRequest)
            else request.db_type
        )
        desc = ""
        if isinstance(request, DatasourceCreateRequest):
            connector_params: BaseDatasourceParameters = (
                self.datasource_manager._create_parameters(request)
            )
            persisted_state = connector_params.persisted_state()
            desc = request.description
        else:
            persisted_state = model_to_dict(request)
            desc = request.comment
        if "ext_config" in persisted_state and isinstance(
            persisted_state["ext_config"], dict
        ):
            persisted_state["ext_config"] = json.dumps(
                persisted_state["ext_config"], ensure_ascii=False
            )
        persisted_state["comment"] = desc
        db_name = persisted_state.get("db_name")
        if not db_name:
            raise HTTPException(status_code=400, detail="datasource name is required")
        datasources = self._dao.get_by_names(db_name)
        if datasources is None:
            raise HTTPException(
                status_code=400,
                detail=f"there is no datasource name:{db_name} exists",
            )
        res = self._dao.update({"id": datasources.id}, persisted_state)
        return self._to_query_response(res)

    def get(self, datasource_id: str) -> Optional[DatasourceQueryResponse]:
        """Get a Flow entity

        Args:
            request (DatasourceServeRequest): The request

        Returns:
            DatasourceServeResponse: The response
        """
        res = self._dao.get_one({"id": datasource_id})
        if not res:
            return None
        return self._to_query_response(res)

    def delete(self, datasource_id: str) -> Optional[DatasourceServeResponse]:
        """Delete a Flow entity

        Args:
            datasource_id (str): The datasource_id

        Returns:
            DatasourceServeResponse: The data after deletion
        """
        db_config = self._dao.get_one({"id": datasource_id})
        if db_config:
            self._db_summary_client.delete_db_profile(db_config.db_name)
            self._dao.delete({"id": datasource_id})
        return db_config

    def get_list(self, db_type: Optional[str] = None) -> List[DatasourceQueryResponse]:
        """List the Flow entities.

        Returns:
            List[DatasourceServeResponse]: The list of responses
        """
        query_request = {}
        if db_type:
            query_request["db_type"] = db_type
        query_list = self.dao.get_list(query_request)
        results = []
        for item in query_list:
            results.append(self._to_query_response(item))
        return results

    def _to_query_response(
        self, res: DatasourceServeResponse
    ) -> DatasourceQueryResponse:
        param_cls = self.datasource_manager._get_param_cls(res.db_type)
        param = param_cls.from_persisted_state(model_to_dict(res))
        param_dict = param.to_dict()
        return DatasourceQueryResponse(
            type=res.db_type,
            params=param_dict,
            description=res.comment,
            id=res.id,
            gmt_created=res.gmt_created,
            gmt_modified=res.gmt_modified,
        )

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

    def refresh(self, datasource_id: str) -> bool:
        """Refresh the datasource.

        Args:
            datasource_id (str): The datasource_id

        Returns:
            bool: The refresh result
        """
        db_config = self._dao.get_one({"id": datasource_id})
        if not db_config:
            raise HTTPException(status_code=404, detail="datasource not found")

        self._db_summary_client.delete_db_profile(db_config.db_name)

        # async embedding
        executor = self._system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()  # type: ignore
        executor.submit(
            self._db_summary_client.db_summary_embedding,
            db_config.db_name,
            db_config.db_type,
        )
        return True
