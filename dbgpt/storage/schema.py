from enum import Enum
import os


class DbInfo:
    def __init__(self, name, is_file_db: bool = False):
        self.name = name
        self.is_file_db = is_file_db


class DBType(Enum):
    Mysql = DbInfo("mysql")
    OCeanBase = DbInfo("oceanbase")
    DuckDb = DbInfo("duckdb", True)
    SQLite = DbInfo("sqlite", True)
    Oracle = DbInfo("oracle")
    MSSQL = DbInfo("mssql")
    Postgresql = DbInfo("postgresql")
    Clickhouse = DbInfo("clickhouse")
    StarRocks = DbInfo("starrocks")
    Spark = DbInfo("spark", True)
    Doris = DbInfo("doris")

    def value(self):
        return self._value_.name

    def is_file_db(self):
        return self._value_.is_file_db

    @staticmethod
    def of_db_type(db_type: str):
        for item in DBType:
            if item.value() == db_type:
                return item
        return None

    @staticmethod
    def parse_file_db_name_from_path(db_type: str, local_db_path: str):
        """Parse out the database name of the embedded database from the file path"""
        base_name = os.path.basename(local_db_path)
        db_name = os.path.splitext(base_name)[0]
        if "." in db_name:
            db_name = os.path.splitext(db_name)[0]
        return db_type + "_" + db_name
