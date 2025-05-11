"""Connection manager."""

import json
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Type

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core.awel.flow import ResourceMetadata
from dbgpt.datasource.base import BaseConnector, BaseDatasourceParameters
from dbgpt.util.annotations import Deprecated
from dbgpt.util.executor_utils import ExecutorFactory
from dbgpt.util.parameter_utils import _get_parameter_descriptions
from dbgpt_ext.datasource.schema import DBType
from dbgpt_serve.core import ResourceParameters, ResourceTypes

from ..api.schemas import DatasourceCreateRequest
from .connect_config_db import ConnectConfigDao
from .db_conn_info import DBConfig

if TYPE_CHECKING:
    # TODO: Don't depend on the rag module.
    from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient

logger = logging.getLogger(__name__)


class ConnectorManager(BaseComponent):
    """Connector manager."""

    name = ComponentType.CONNECTOR_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new ConnectorManager."""
        self.storage = ConnectConfigDao()
        self.system_app = system_app
        self._db_summary_client: Optional["DBSummaryClient"] = None
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Init component."""
        self.system_app = system_app

    def on_init(self):
        """Execute on init.

        Load all connector classes.
        """
        from dbgpt.datasource.rdbms.base import RDBMSConnector  # noqa: F401
        from dbgpt_ext.datasource.conn_spark import SparkConnector  # noqa: F401
        from dbgpt_ext.datasource.conn_tugraph import TuGraphConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_clickhouse import (  # noqa: F401
            ClickhouseConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_doris import DorisConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_duckdb import DuckDbConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_hive import HiveConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_mssql import MSSQLConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_oceanbase import (  # noqa: F401
            OceanBaseConnector,
        )

        # 添加OracleConnector导入
        from dbgpt_ext.datasource.rdbms.conn_oracle import OracleConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_postgresql import (  # noqa: F401
            PostgreSQLConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_starrocks import (  # noqa: F401
            StarRocksConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_vertica import (  # noqa: F401
            VerticaConnector,
        )
        from dbgpt_ext.datasource.rdbms.dialect.oceanbase.ob_dialect import (  # noqa: F401
            OBDialect,
        )

        from .connect_config_db import ConnectConfigEntity  # noqa: F401

    def before_start(self):
        """Execute before start."""
        from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient

        self._db_summary_client = DBSummaryClient(self.system_app)

    @property
    def db_summary_client(self) -> "DBSummaryClient":
        """Get DBSummaryClient."""
        if not self._db_summary_client:
            raise ValueError("DBSummaryClient is not initialized")
        return self._db_summary_client

    def _get_all_subclasses(
        self, cls: Type[BaseConnector]
    ) -> List[Type[BaseConnector]]:
        """Get all subclasses of cls."""
        subclasses = cls.__subclasses__()
        for subclass in subclasses:
            subclasses += self._get_all_subclasses(subclass)
        return subclasses

    @Deprecated(
        version="0.7.0", remove_version="0.8.0", alternative="get_supported_types"
    )
    def get_all_completed_types(self) -> List[DBType]:
        """Get all completed types."""
        chat_classes = self._get_all_subclasses(BaseConnector)  # type: ignore
        support_types = []
        for cls in chat_classes:
            if cls.db_type and cls.is_normal_type():
                db_type = DBType.of_db_type(cls.db_type)
                if db_type:
                    support_types.append(db_type)
        return support_types

    def get_supported_types(self) -> ResourceTypes:
        """Get supported types."""

        chat_classes = self._get_all_subclasses(BaseConnector)  # type: ignore
        support_type_params = []
        for cls in chat_classes:
            if cls.db_type and cls.is_normal_type():
                db_type = DBType.of_db_type(cls.db_type)
                if not db_type:
                    continue
                param_cls = cls.param_class()
                parameters = _get_parameter_descriptions(param_cls)
                label = db_type.value()
                description = label
                metadata_name = f"_resource_metadata_{param_cls.__name__}"
                if hasattr(param_cls, metadata_name):
                    flow_metadata: ResourceMetadata = getattr(param_cls, metadata_name)
                    label = flow_metadata.label
                    description = flow_metadata.description
                support_type_params.append(
                    ResourceParameters(
                        name=db_type.value(),
                        label=label,
                        description=description,
                        parameters=parameters,
                    )
                )
        return ResourceTypes(types=support_type_params)

    def _supported_types(self) -> Dict[str, Type[BaseConnector]]:
        """Get supported types."""
        chat_classes = self._get_all_subclasses(BaseConnector)
        support_types = {}
        for cls in chat_classes:
            if cls.db_type and cls.is_normal_type():
                db_type = DBType.of_db_type(cls.db_type)
                if db_type:
                    support_types[db_type.value()] = cls
        return support_types

    def get_cls_by_dbtype(self, db_type) -> Type[BaseConnector]:
        """Get class by db type."""
        chat_classes = self._get_all_subclasses(BaseConnector)  # type: ignore
        result = None
        for cls in chat_classes:
            if cls.db_type == db_type and cls.is_normal_type():
                result = cls
        if not result:
            raise ValueError("Unsupported Db Type！" + db_type)
        return result

    def get_connector(self, db_name: str):
        """Create a new connection instance.

        Args:
            db_name (str): database name
        """
        db_config = self.storage.get_db_config(db_name)
        db_type = DBType.of_db_type(db_config.get("db_type"))
        if not db_type:
            raise ValueError("Unsupported Db Type！" + db_config.get("db_type"))
        connect_instance = self.get_cls_by_dbtype(db_type.value())
        if db_type.is_file_db():
            db_path = db_config.get("db_path")
            return connect_instance.from_file_path(db_path)  # type: ignore
        elif db_type.value() == "oracle":
            logger.info("-------------Oracle Datasource------------")
            host = db_config.get("db_host")
            port = db_config.get("db_port")
            user = db_config.get("db_user")
            pwd = db_config.get("db_pwd")
            extConfig = db_config.get("ext_config")
            dbJson = json.loads(extConfig)
            service_name = dbJson.get("service_name", None)
            sid = (dbJson.get("sid", None),)
            return connect_instance.from_uri_db(  # type: ignore
                host=host, port=port, user=user, pwd=pwd, service_name=service_name
            )
        else:
            db_host = db_config.get("db_host")
            db_port = db_config.get("db_port")
            db_user = db_config.get("db_user")
            db_pwd = db_config.get("db_pwd")
            return connect_instance.from_uri_db(  # type: ignore
                host=db_host, port=db_port, user=db_user, pwd=db_pwd, db_name=db_name
            )

    def _create_parameters(
        self, request: DatasourceCreateRequest
    ) -> BaseDatasourceParameters:
        """Create parameters."""
        db_type = DBType.of_db_type(request.type)
        if not db_type:
            raise ValueError("Unsupported Db Type！" + request.type)
        support_types = self._supported_types()
        if db_type.value() not in support_types:
            raise ValueError("Unsupported Db Type！" + request.type)
        cls = support_types[db_type.value()]
        param_cls = cls.param_class()
        # ignore_extra_fields is used to ignore extra fields in the request
        return param_cls.from_dict(request.params, ignore_extra_fields=True)

    def _get_param_cls(self, db_type: str) -> Type[BaseDatasourceParameters]:
        """Get param class."""
        support_types = self._supported_types()
        if db_type not in support_types:
            raise ValueError("Unsupported Db Type！" + db_type)
        cls = support_types[db_type]
        return cls.param_class()

    def create_connector(self, param: BaseDatasourceParameters) -> BaseConnector:
        """Create a new connector instance."""
        return param.create_connector()

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
        alternative="test_connection",
    )
    def test_connect(self, db_info: DBConfig) -> BaseConnector:
        """Test connectivity.

        (Deprecated) Use test_connection instead.

        Args:
            db_info (DBConfig): db connect info.

        Returns:
            BaseConnector: connector instance.

        Raises:
            ValueError: Test connect Failure.
        """
        try:
            db_type = DBType.of_db_type(db_info.db_type)
            if not db_type:
                raise ValueError("Unsupported Db Type！" + db_info.db_type)
            connect_instance = self.get_cls_by_dbtype(db_type.value())
            if db_type.is_file_db():
                db_path = db_info.file_path
                return connect_instance.from_file_path(db_path)  # type: ignore
            else:
                db_name = db_info.db_name
                db_host = db_info.db_host
                db_port = db_info.db_port
                db_user = db_info.db_user
                db_pwd = db_info.db_pwd
                return connect_instance.from_uri_db(  # type: ignore
                    host=db_host,
                    port=db_port,
                    user=db_user,
                    pwd=db_pwd,
                    db_name=db_name,
                )
        except Exception as e:
            logger.error(f"{db_info.db_name} Test connect Failure!{str(e)}")
            raise ValueError(f"{db_info.db_name} Test connect Failure!{str(e)}")

    def test_connection(self, request: DatasourceCreateRequest) -> bool:
        """Test connection.

        Args:
            request (DatasourceCreateRequest): The request.

        Returns:
            bool: True if connection is successful.
        """
        try:
            param = self._create_parameters(request)
            _connector = self.create_connector(param)
            return True
        except Exception as e:
            logger.error(f"Test connection Failure!{str(e)}")
            raise ValueError(f"Test connection Failure!{str(e)}")

    def get_db_list(self, db_name: Optional[str] = None, user_id: Optional[str] = None):
        """Get db list."""
        return self.storage.get_db_list(db_name, user_id)

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
    )
    def delete_db(self, db_name: str):
        """Delete db connect info."""
        return self.storage.delete_db(db_name)

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
    )
    def edit_db(self, db_info: DBConfig):
        """Edit db connect info."""
        return self.storage.update_db_info(
            db_info.db_name,
            db_info.db_type,
            db_info.file_path,
            db_info.db_host,
            db_info.db_port,
            db_info.db_user,
            db_info.db_pwd,
            db_info.comment,
        )

    async def async_db_summary_embedding(self, db_name, db_type):
        """Async db summary embedding."""
        executor = self.system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()  # type: ignore
        executor.submit(self.db_summary_client.db_summary_embedding, db_name, db_type)
        return True

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
    )
    def add_db(self, db_info: DBConfig, user_id: Optional[str] = None):
        """Add db connect info.

        Args:
            db_info (DBConfig): db connect info.
        """
        logger.info(f"add_db:{db_info.__dict__}")
        try:
            db_type = DBType.of_db_type(db_info.db_type)
            if not db_type:
                raise ValueError("Unsupported Db Type！" + db_info.db_type)
            if db_type.is_file_db():
                self.storage.add_file_db(
                    db_info.db_name,
                    db_info.db_type,
                    db_info.file_path,
                    db_info.comment,
                    user_id,
                )
            else:
                self.storage.add_url_db(
                    db_info.db_name,
                    db_info.db_type,
                    db_info.db_host,
                    db_info.db_port,
                    db_info.db_user,
                    db_info.db_pwd,
                    db_info.comment,
                    user_id,
                )
            # async embedding
            executor = self.system_app.get_component(
                ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
            ).create()  # type: ignore
            executor.submit(
                self.db_summary_client.db_summary_embedding,
                db_info.db_name,
                db_info.db_type,
            )
        except Exception as e:
            raise ValueError("Add db connect info error!" + str(e))

        return True
