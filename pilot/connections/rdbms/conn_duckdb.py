from typing import Optional, Any, Iterable
from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.ext.declarative import declarative_base

from pilot.connections.rdbms.rdbms_connect import RDBMSDatabase
from pilot.configs.config import Config

CFG = Config()
Base = declarative_base()

class DuckDbConnect(RDBMSDatabase):
    """Connect Duckdb Database fetch MetaData
    Args:
    Usage:
    """
    db_type: str = "duckdb"
    db_dialect: str = "duckdb"

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSDatabase:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine("duckdb:///" + file_path, **_engine_args), **kwargs)

    def table_simple_info(self) -> Iterable[str]:
        _tables_sql = f"""
                SELECT name FROM sqlite_master WHERE type='table'
            """
        cursor = self.session.execute(text(_tables_sql))
        tables_results = cursor.fetchall()
        results =[]
        for row in tables_results:
            table_name = row[0]
            _sql = f"""
                PRAGMA  table_info({table_name})
            """
            cursor_colums = self.session.execute(text(_sql))
            colum_results = cursor_colums.fetchall()
            table_colums = []
            for row_col in colum_results:
                field_info = list(row_col)
                table_colums.append(field_info[1])

            results.append(f"{table_name}({','.join(table_colums)});")
        return results

if __name__ == "__main__":
    engine = create_engine('duckdb:////Users/tuyang.yhj/Code/PycharmProjects/DB-GPT/pilot/mock_datas/db-gpt-test.db')
    metadata = MetaData(engine)

    results = engine.connect().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

    print(str(results))

    fields = []
    results2 = engine.connect().execute(f"""PRAGMA  table_info(user)""").fetchall()
    for row_col in results2:
        field_info = list(row_col)
        fields.append(field_info[1])
    print(str(fields))
