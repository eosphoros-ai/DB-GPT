#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Optional, Any, Iterable
from sqlalchemy import create_engine, text
import tempfile
import logging
from dbgpt.datasource.rdbms.base import RDBMSDatabase

logger = logging.getLogger(__name__)


class SQLiteConnect(RDBMSDatabase):
    """Connect SQLite Database fetch MetaData
    Args:
    Usage:
    """

    db_type: str = "sqlite"
    db_dialect: str = "sqlite"

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSDatabase:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        _engine_args["connect_args"] = {"check_same_thread": False}
        # _engine_args["echo"] = True
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        return cls(create_engine("sqlite:///" + file_path, **_engine_args), **kwargs)

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        cursor = self.session.execute(text(f"PRAGMA index_list({table_name})"))
        indexes = cursor.fetchall()
        return [(index[1], index[3]) for index in indexes]

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        cursor = self.session.execute(
            text(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            )
        )
        ans = cursor.fetchall()
        return ans[0][0]

    def get_fields(self, table_name):
        """Get column fields about specified table."""
        cursor = self.session.execute(text(f"PRAGMA table_info('{table_name}')"))
        fields = cursor.fetchall()
        print(fields)
        return [(field[1], field[2], field[3], field[4], field[5]) for field in fields]

    def get_users(self):
        return []

    def get_grants(self):
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        return "UTF-8"

    def get_database_list(self):
        return []

    def get_database_names(self):
        return []

    def _sync_tables_from_db(self) -> Iterable[str]:
        table_results = self.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        view_results = self.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='view'")
        )
        table_results = set(row[0] for row in table_results)
        view_results = set(row[0] for row in view_results)
        self._all_tables = table_results.union(view_results)
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def _write(self, session, write_sql):
        print(f"Write[{write_sql}]")
        result = session.execute(text(write_sql))
        session.commit()
        # TODO  Subsequent optimization of dynamically specified database submission loss target problem
        print(f"SQL[{write_sql}], result:{result.rowcount}")
        return result.rowcount

    def get_table_comments(self, db_name=None):
        cursor = self.session.execute(
            text(
                f"""
                SELECT name, sql FROM sqlite_master WHERE type='table'
                """
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]

    def table_simple_info(self) -> Iterable[str]:
        _tables_sql = f"""
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


class SQLiteTempConnect(SQLiteConnect):
    """A temporary SQLite database connection. The database file will be deleted when the connection is closed."""

    def __init__(self, engine, temp_file_path, *args, **kwargs):
        super().__init__(engine, *args, **kwargs)
        self.temp_file_path = temp_file_path
        self._is_closed = False

    @classmethod
    def create_temporary_db(
        cls, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> "SQLiteTempConnect":
        """Create a temporary SQLite database with a temporary file.

        Examples:
            .. code-block:: python
                with SQLiteTempConnect.create_temporary_db() as db:
                    db.run(db.session, "CREATE TABLE test (id INTEGER PRIMARY KEY);")
                    db.run(db.session, "insert into test(id) values (1)")
                    db.run(db.session, "insert into test(id) values (2)")
                    field_names, result = db.query_ex(db.session, "select * from test")
                    assert field_names == ["id"]
                    assert result == [(1,), (2,)]

        Args:
            engine_args (Optional[dict]): SQLAlchemy engine arguments.

        Returns:
            SQLiteTempConnect: A SQLiteTempConnect instance.
        """
        _engine_args = engine_args or {}
        _engine_args["connect_args"] = {"check_same_thread": False}

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_path = temp_file.name
        temp_file.close()

        engine = create_engine(f"sqlite:///{temp_file_path}", **_engine_args)
        return cls(engine, temp_file_path, **kwargs)

    def close(self):
        """Close the connection."""
        if not self._is_closed:
            if self._engine:
                self._engine.dispose()
            try:
                if os.path.exists(self.temp_file_path):
                    os.remove(self.temp_file_path)
            except Exception as e:
                logger.error(f"Error removing temporary database file: {e}")
            self._is_closed = True

    def create_temp_tables(self, tables_info):
        """Create temporary tables with data.

        Examples:
            .. code-block:: python
                tables_info = {
                    "test": {
                        "columns": {
                            "id": "INTEGER PRIMARY KEY",
                            "name": "TEXT",
                            "age": "INTEGER",
                        },
                        "data": [
                            (1, "Tom", 20),
                            (2, "Jack", 21),
                            (3, "Alice", 22),
                        ],
                    },
                }
                with SQLiteTempConnect.create_temporary_db() as db:
                    db.create_temp_tables(tables_info)
                    field_names, result = db.query_ex(db.session, "select * from test")
                    assert field_names == ["id", "name", "age"]
                    assert result == [(1, "Tom", 20), (2, "Jack", 21), (3, "Alice", 22)]

        Args:
            tables_info (dict): A dictionary of table information.
        """
        for table_name, table_data in tables_info.items():
            columns = ", ".join(
                [f"{col} {dtype}" for col, dtype in table_data["columns"].items()]
            )
            create_sql = f"CREATE TABLE {table_name} ({columns});"
            self.session.execute(text(create_sql))
            for row in table_data.get("data", []):
                placeholders = ", ".join(
                    [":param" + str(index) for index, _ in enumerate(row)]
                )
                insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders});"

                param_dict = {
                    "param" + str(index): value for index, value in enumerate(row)
                }
                self.session.execute(text(insert_sql), param_dict)
            self.session.commit()
        self._sync_tables_from_db()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    @classmethod
    def is_normal_type(cls) -> bool:
        return False
