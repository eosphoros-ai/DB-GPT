#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Optional, Any, Iterable
from sqlalchemy import create_engine, text

from dbgpt.datasource.rdbms.base import RDBMSDatabase


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
