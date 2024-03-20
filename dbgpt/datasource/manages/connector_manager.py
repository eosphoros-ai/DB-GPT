"""Connection manager."""
import logging
from typing import TYPE_CHECKING, List, Optional, Type

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.storage.schema import DBType
from dbgpt.util.executor_utils import ExecutorFactory

from ..base import BaseConnector
from ..db_conn_info import DBConfig
from .connect_config_db import ConnectConfigDao

if TYPE_CHECKING:
    # TODO: Don't depend on the rag module.
    from dbgpt.rag.summary.db_summary_client import DBSummaryClient

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
        from dbgpt.datasource.conn_spark import SparkConnector  # noqa: F401
        from dbgpt.datasource.rdbms.base import RDBMSConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_clickhouse import (  # noqa: F401
            ClickhouseConnector,
        )
        from dbgpt.datasource.rdbms.conn_doris import DorisConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_duckdb import DuckDbConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_hive import HiveConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_mssql import MSSQLConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_mysql import MySQLConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_postgresql import (  # noqa: F401
            PostgreSQLConnector,
        )
        from dbgpt.datasource.rdbms.conn_sqlite import SQLiteConnector  # noqa: F401
        from dbgpt.datasource.rdbms.conn_starrocks import (  # noqa: F401
            StarRocksConnector,
        )

        from .connect_config_db import ConnectConfigEntity  # noqa: F401

    def before_start(self):
        """Execute before start."""
        from dbgpt.rag.summary.db_summary_client import DBSummaryClient

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
        else:
            db_host = db_config.get("db_host")
            db_port = db_config.get("db_port")
            db_user = db_config.get("db_user")
            db_pwd = db_config.get("db_pwd")
            return connect_instance.from_uri_db(  # type: ignore
                host=db_host, port=db_port, user=db_user, pwd=db_pwd, db_name=db_name
            )

    def test_connect(self, db_info: DBConfig) -> BaseConnector:
        """Test connectivity.

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

    def get_db_list(self):
        """Get db list."""
        return self.storage.get_db_list()

    def delete_db(self, db_name: str):
        """Delete db connect info."""
        return self.storage.delete_db(db_name)

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
        # TODO: async embedding
        self.db_summary_client.db_summary_embedding(db_name, db_type)

    def add_db(self, db_info: DBConfig):
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
                    db_info.db_name, db_info.db_type, db_info.file_path
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
