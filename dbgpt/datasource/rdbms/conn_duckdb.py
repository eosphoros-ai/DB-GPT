"""DuckDB connector."""
from typing import Any, Iterable, Optional

from sqlalchemy import create_engine, text

from .base import RDBMSConnector


class DuckDbConnector(RDBMSConnector):
    """DuckDB connector."""

    db_type: str = "duckdb"
    db_dialect: str = "duckdb"

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSConnector:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine("duckdb:///" + file_path, **_engine_args), **kwargs)

    def get_users(self):
        """Get users."""
        cursor = self.session.execute(
            text(
                "SELECT * FROM sqlite_master WHERE type = 'table' AND "
                "name = 'duckdb_sys_users';"
            )
        )
        users = cursor.fetchall()
        return [(user[0], user[1]) for user in users]

    def get_grants(self):
        """Get grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get character_set of current database."""
        return "UTF-8"

    def get_table_comments(self, db_name: str):
        """Get table comments."""
        cursor = self.session.execute(
            text(
                """
                SELECT name, sql FROM sqlite_master WHERE type='table'
                """
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]

    def table_simple_info(self) -> Iterable[str]:
        """Get table simple info."""
        _tables_sql = """
                SELECT name FROM sqlite_master WHERE type='table'
            """
        cursor = self.session.execute(text(_tables_sql))
        tables_results = cursor.fetchall()
        results = []
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
