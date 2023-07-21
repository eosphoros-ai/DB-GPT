from enum import auto, Enum
from typing import List, Any


class SeparatorStyle(Enum):
    SINGLE = "###"
    TWO = "</s>"
    THREE = auto()
    FOUR = auto()


class ExampleType(Enum):
    ONE_SHOT = "one_shot"
    FEW_SHOT = "few_shot"


class DbInfo:
    def __init__(self, name, is_file_db: bool = False):
        self.name = name
        self.is_file_db = is_file_db


class DBType(Enum):
    Mysql = DbInfo("mysql")
    OCeanBase = DbInfo("oceanbase")
    DuckDb = DbInfo("duckdb", True)
    Oracle = DbInfo("oracle")
    MSSQL = DbInfo("mssql")
    Postgresql = DbInfo("postgresql")

    def value(self):
        return self._value_.name;

    def is_file_db(self):
        return self._value_.is_file_db

    @staticmethod
    def of_db_type(db_type: str):
        for item in DBType:
            if item.value() == db_type:
                return item
        return None
