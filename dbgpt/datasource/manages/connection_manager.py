from typing import List, Type
from dbgpt.datasource import ConnectConfigDao
from dbgpt.storage.schema import DBType
from dbgpt.component import SystemApp, ComponentType
from dbgpt.util.executor_utils import ExecutorFactory

from dbgpt.datasource.db_conn_info import DBConfig
from dbgpt.rag.summary.db_summary_client import DBSummaryClient
from dbgpt.datasource.base import BaseConnect
from dbgpt.datasource.rdbms.conn_mysql import MySQLConnect
from dbgpt.datasource.rdbms.conn_duckdb import DuckDbConnect
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteConnect
from dbgpt.datasource.rdbms.conn_mssql import MSSQLConnect
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.datasource.rdbms.conn_clickhouse import ClickhouseConnect
from dbgpt.datasource.rdbms.conn_postgresql import PostgreSQLDatabase
from dbgpt.datasource.rdbms.conn_starrocks import StarRocksConnect
from dbgpt.datasource.conn_spark import SparkConnect
from dbgpt.datasource.rdbms.conn_doris import DorisConnect


class ConnectManager:
    """db connect manager"""

    def get_all_subclasses(self, cls: Type[BaseConnect]) -> List[Type[BaseConnect]]:
        subclasses = cls.__subclasses__()
        for subclass in subclasses:
            subclasses += self.get_all_subclasses(subclass)
        return subclasses

    def get_all_completed_types(self):
        chat_classes = self.get_all_subclasses(BaseConnect)
        support_types = []
        for cls in chat_classes:
            if cls.db_type and cls.is_normal_type():
                support_types.append(DBType.of_db_type(cls.db_type))
        return support_types

    def get_cls_by_dbtype(self, db_type):
        chat_classes = self.get_all_subclasses(BaseConnect)
        result = None
        for cls in chat_classes:
            if cls.db_type == db_type and cls.is_normal_type():
                result = cls
        if not result:
            raise ValueError("Unsupported Db Type！" + db_type)
        return result

    def __init__(self, system_app: SystemApp):
        """metadata database management initialization"""
        # self.storage = DuckdbConnectConfig()
        self.storage = ConnectConfigDao()
        self.system_app = system_app
        self.db_summary_client = DBSummaryClient(system_app)

    def get_connect(self, db_name):
        db_config = self.storage.get_db_config(db_name)
        db_type = DBType.of_db_type(db_config.get("db_type"))
        connect_instance = self.get_cls_by_dbtype(db_type.value())
        if db_type.is_file_db():
            db_path = db_config.get("db_path")
            return connect_instance.from_file_path(db_path)
        else:
            db_host = db_config.get("db_host")
            db_port = db_config.get("db_port")
            db_user = db_config.get("db_user")
            db_pwd = db_config.get("db_pwd")
            return connect_instance.from_uri_db(
                host=db_host, port=db_port, user=db_user, pwd=db_pwd, db_name=db_name
            )

    def test_connect(self, db_info: DBConfig):
        try:
            db_type = DBType.of_db_type(db_info.db_type)
            connect_instance = self.get_cls_by_dbtype(db_type.value())
            if db_type.is_file_db():
                db_path = db_info.file_path
                return connect_instance.from_file_path(db_path)
            else:
                db_name = db_info.db_name
                db_host = db_info.db_host
                db_port = db_info.db_port
                db_user = db_info.db_user
                db_pwd = db_info.db_pwd
                return connect_instance.from_uri_db(
                    host=db_host,
                    port=db_port,
                    user=db_user,
                    pwd=db_pwd,
                    db_name=db_name,
                )
        except Exception as e:
            print(f"{db_info.db_name} Test connect Failure!{str(e)}")
            raise ValueError(f"{db_info.db_name} Test connect Failure!{str(e)}")

    def get_db_list(self):
        return self.storage.get_db_list()

    def get_db_names(self):
        return self.storage.get_by_name()

    def delete_db(self, db_name: str):
        return self.storage.delete_db(db_name)

    def edit_db(self, db_info: DBConfig):
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
        # 在这里执行需要异步运行的代码
        self.db_summary_client.db_summary_embedding(db_name, db_type)

    def add_db(self, db_info: DBConfig):
        print(f"add_db:{db_info.__dict__}")
        try:
            db_type = DBType.of_db_type(db_info.db_type)
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
            ).create()
            executor.submit(
                self.db_summary_client.db_summary_embedding,
                db_info.db_name,
                db_info.db_type,
            )
        except Exception as e:
            raise ValueError("Add db connect info error!" + str(e))

        return True
