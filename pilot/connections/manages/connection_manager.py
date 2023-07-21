from pilot.configs.config import Config
from pilot.connections.manages.connect_storage_duckdb import DuckdbConnectConfig
from pilot.common.schema import DBType
from pilot.connections.rdbms.conn_mysql import MySQLConnect
from pilot.connections.base import BaseConnect

from pilot.connections.rdbms.conn_mysql import MySQLConnect
from pilot.connections.rdbms.conn_duckdb import DuckDbConnect
from pilot.connections.rdbms.rdbms_connect import RDBMSDatabase
from pilot.singleton import Singleton
from pilot.common.sql_database import Database

CFG = Config()


class ConnectManager:


    def get_all_subclasses(self, cls):
        subclasses = cls.__subclasses__()
        for subclass in subclasses:
            subclasses += self.get_all_subclasses(subclass)
        return subclasses

    def get_cls_by_dbtype(self, db_type):
        chat_classes = self.get_all_subclasses(BaseConnect)
        result = None
        for cls in chat_classes:
            if cls.db_type == db_type:
                result = cls
        if not result:
            raise ValueError("Unsupport Db Type！" + db_type)
        return result

    def __init__(self):
        self.storage = DuckdbConnectConfig()
        self.__load_config_db()

    def __load_config_db(self):
        if CFG.LOCAL_DB_HOST:
            # default mysql
            if CFG.LOCAL_DB_NAME:
                self.storage.add_url_db(CFG.LOCAL_DB_NAME, DBType.Mysql.value(), CFG.LOCAL_DB_HOST, CFG.LOCAL_DB_PORT,
                                        CFG.LOCAL_DB_USER, CFG.LOCAL_DB_PASSWORD, "")
            else:
                # get all default mysql database
                default_mysql = Database.from_uri(
                    "mysql+pymysql://"
                    + CFG.LOCAL_DB_USER
                    + ":"
                    + CFG.LOCAL_DB_PASSWORD
                    + "@"
                    + CFG.LOCAL_DB_HOST
                    + ":"
                    + str(CFG.LOCAL_DB_PORT),
                    engine_args={"pool_size": 10, "pool_recycle": 3600, "echo": True},
                )
                # default_mysql = MySQLConnect.from_uri(
                #     "mysql+pymysql://"
                #     + CFG.LOCAL_DB_USER
                #     + ":"
                #     + CFG.LOCAL_DB_PASSWORD
                #     + "@"
                #     + CFG.LOCAL_DB_HOST
                #     + ":"
                #     + str(CFG.LOCAL_DB_PORT),
                #     engine_args={"pool_size": 10, "pool_recycle": 3600, "echo": True},
                # )
                dbs = default_mysql.get_database_list()
                for name in dbs:
                    self.storage.add_url_db(name, DBType.Mysql.value(), CFG.LOCAL_DB_HOST, CFG.LOCAL_DB_PORT,
                                            CFG.LOCAL_DB_USER, CFG.LOCAL_DB_PASSWORD, "")
        if CFG.LOCAL_DB_PATH:
            # default file db is duckdb
            db_name = self.storage.get_file_db_name(CFG.LOCAL_DB_PATH)
            if db_name:
                self.storage.add_file_db(db_name, DBType.DuckDb.value(), CFG.LOCAL_DB_PATH)

    def get_connect(self, db_name):
        db_config = self.storage.get_db_config(db_name)
        db_type = DBType.of_db_type(db_config.get('db_type'))
        connect_instance = self.get_cls_by_dbtype(db_type.value())
        if db_type.is_file_db():
            db_path = db_config.get('db_path')
            return connect_instance.from_file_path(db_path)
        else:
            db_host = db_config.get('db_host')
            db_port = db_config.get('db_port')
            db_user = db_config.get('db_user')
            db_pwd = db_config.get('db_pwd')
            return connect_instance.from_uri_db(db_host, db_port, db_user, db_pwd, db_name)

    def get_db_list(self):
        return self.storage.get_db_list()

    def get_db_names(self):
        return self.storage.get_db_names()
