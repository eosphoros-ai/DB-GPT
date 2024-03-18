"""SQLite connector."""
import logging
import os
import tempfile
from typing import Any, Iterable, List, Optional, Tuple

from sqlalchemy import create_engine, text

from .base import RDBMSConnector

logger = logging.getLogger(__name__)


class SQLiteConnector(RDBMSConnector):
    """SQLite connector."""

    db_type: str = "sqlite"
    db_dialect: str = "sqlite"

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> "SQLiteConnector":
        """Create a new SQLiteConnector from file path."""
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
        result = []
        for idx in indexes:
            index_name = idx[1]
            cursor = self.session.execute(text(f"PRAGMA index_info({index_name})"))
            index_infos = cursor.fetchall()
            column_names = [index_info[2] for index_info in index_infos]
            result.append({"name": index_name, "column_names": column_names})
        return result

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        cursor = self.session.execute(
            text(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                f"AND name='{table_name}'"
            )
        )
        ans = cursor.fetchall()
        return ans[0][0]

    def get_fields(self, table_name) -> List[Tuple]:
        """Get column fields about specified table."""
        cursor = self.session.execute(text(f"PRAGMA table_info('{table_name}')"))
        fields = cursor.fetchall()
        logger.info(fields)
        return [(field[1], field[2], field[3], field[4], field[5]) for field in fields]

    def get_simple_fields(self, table_name):
        """Get column fields about specified table."""
        return self.get_fields(table_name)

    def get_users(self):
        """Get user info."""
        return []

    def get_grants(self):
        """Get grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get character_set of current database."""
        return "UTF-8"

    def get_database_names(self):
        """Get database names."""
        return []

    def _sync_tables_from_db(self) -> Iterable[str]:
        table_results = self.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        view_results = self.session.execute(
            text("SELECT name FROM sqlite_master WHERE type='view'")
        )
        table_results = set(row[0] for row in table_results)  # noqa
        view_results = set(row[0] for row in view_results)  # noqa
        self._all_tables = table_results.union(view_results)
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def _write(self, write_sql):
        logger.info(f"Write[{write_sql}]")
        session = self.session
        result = session.execute(text(write_sql))
        session.commit()
        # TODO  Subsequent optimization of dynamically specified database submission
        #  loss target problem
        logger.info(f"SQL[{write_sql}], result:{result.rowcount}")
        return result.rowcount

    def get_table_comments(self, db_name=None):
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


class SQLiteTempConnector(SQLiteConnector):
    """A temporary SQLite database connection.

    The database file will be deleted when the connection is closed.
    """

    def __init__(self, engine, temp_file_path, *args, **kwargs):
        """Construct a temporary SQLite database connection."""
        super().__init__(engine, *args, **kwargs)
        self.temp_file_path = temp_file_path
        self._is_closed = False

    @classmethod
    def create_temporary_db(
        cls, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> "SQLiteTempConnector":
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
            SQLiteTempConnector: A SQLiteTempConnect instance.
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
                with SQLiteTempConnector.create_temporary_db() as db:
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
        """Return the connection when entering the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the connection when exiting the context manager."""
        self.close()

    def __del__(self):
        """Close the connection when the object is deleted."""
        self.close()

    @classmethod
    def is_normal_type(cls) -> bool:
        """Return whether the connector is a normal type."""
        return False
