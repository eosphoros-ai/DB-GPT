"""SQLite connector."""

import dataclasses
import logging
import os
import tempfile
from typing import Any, Iterable, List, Optional, Tuple, Type

from sqlalchemy import create_engine, text

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("SQLite datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Lightweight embedded relational database with simplicity and portability."
    ),
)
@dataclasses.dataclass
class SQLiteConnectorParameters(BaseDatasourceParameters):
    """SQLite connector parameters.

    This class defines the configuration parameters for SQLite database connections.
    It provides various options to customize the connection behavior and database
    settings.
    """

    __type__ = "sqlite"

    path: str = dataclasses.field(
        metadata={
            "help": _(
                "SQLite database file path. Use ':memory:' for in-memory database"
            ),
            "required": True,
        }
    )
    check_same_thread: bool = dataclasses.field(
        default=False,
        metadata={
            "help": _(
                "Check same thread or not, default is False. Set False to allow "
                "sharing connection across threads"
            )
        },
    )

    driver: str = dataclasses.field(
        default="sqlite", metadata={"help": _("Driver name, default is sqlite")}
    )

    def create_connector(self) -> "SQLiteConnector":
        """Create SQLite connector."""
        return SQLiteConnector.from_parameters(self)

    def db_url(self, ssl: bool = False, charset: Optional[str] = None):
        return f"{self.driver}:///{self.path}"


class SQLiteConnector(RDBMSConnector):
    """SQLite connector."""

    db_type: str = "sqlite"
    db_dialect: str = "sqlite"

    @classmethod
    def param_class(cls) -> Type[SQLiteConnectorParameters]:
        """Return parameter class."""
        return SQLiteConnectorParameters

    @classmethod
    def from_parameters(
        cls, parameters: SQLiteConnectorParameters
    ) -> "SQLiteConnector":
        """Create a new SQLiteConnector from parameters."""
        _engine_args = {
            "connect_args": {"check_same_thread": parameters.check_same_thread}
        }
        return cls(create_engine(f"sqlite:///{parameters.path}", **_engine_args))

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
        with self.session_scope() as session:
            cursor = session.execute(text(f"PRAGMA index_list({table_name})"))
            indexes = cursor.fetchall()
            result = []
            for idx in indexes:
                index_name = idx[1]
                cursor = session.execute(text(f"PRAGMA index_info({index_name})"))
                index_infos = cursor.fetchall()
                column_names = [index_info[2] for index_info in index_infos]
                result.append({"name": index_name, "column_names": column_names})
            return result

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT sql FROM sqlite_master WHERE type='table' "
                    f"AND name='{table_name}'"
                )
            )
            ans = cursor.fetchall()
            return ans[0][0]

    def get_fields(self, table_name, db_name=None) -> List[Tuple]:
        """Get column fields about specified table."""
        with self.session_scope() as session:
            cursor = session.execute(text(f"PRAGMA table_info('{table_name}')"))
            fields = cursor.fetchall()
            logger.info(fields)
            return [
                (field[1], field[2], field[3], field[4], field[5]) for field in fields
            ]

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
        """Sync tables from database."""
        with self.session_scope() as session:
            table_results = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            view_results = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='view'")
            )
            table_results = set(row[0] for row in table_results)  # noqa
            view_results = set(row[0] for row in view_results)  # noqa
            self._all_tables = table_results.union(view_results)
            self._metadata.reflect(bind=self._engine)
            return self._all_tables

    def _write(self, write_sql):
        logger.info(f"Write[{write_sql}]")
        with self.session_scope() as session:
            result = session.execute(text(write_sql))
            # TODO  Subsequent optimization of dynamically specified database submission
            #  loss target problem
            logger.info(f"SQL[{write_sql}], result:{result.rowcount}")
            return result.rowcount

    def get_table_comments(self, db_name=None):
        """Get table comments."""
        with self.session_scope() as session:
            cursor = session.execute(
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

    def get_current_db_name(self) -> str:
        """Get current database name.

        Returns:
            str: database name
        """
        full_path = self._engine.url.database
        db_name = os.path.basename(full_path)
        if db_name.endswith(".db"):
            db_name = db_name[:-3]
        return db_name

    def table_simple_info(self) -> Iterable[str]:
        """Get table simple info."""
        _tables_sql = """
                SELECT name FROM sqlite_master WHERE type='table'
            """
        with self.session_scope() as session:
            cursor = session.execute(text(_tables_sql))
            tables_results = cursor.fetchall()
            results = []
            for row in tables_results:
                table_name = row[0]
                _sql = f"""
                    PRAGMA  table_info({table_name})
                """
                cursor_colums = session.execute(text(_sql))
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
        try:
            if os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
            super().close()
        except Exception as e:
            logger.error(f"Error removing temporary database file: {e}")

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
        with self.session_scope() as session:
            for table_name, table_data in tables_info.items():
                columns = ", ".join(
                    [f"{col} {dtype}" for col, dtype in table_data["columns"].items()]
                )
                create_sql = f"CREATE TABLE {table_name} ({columns});"
                session.execute(text(create_sql))
                for row in table_data.get("data", []):
                    placeholders = ", ".join(
                        [":param" + str(index) for index, _ in enumerate(row)]
                    )
                    insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders});"

                    param_dict = {
                        "param" + str(index): value for index, value in enumerate(row)
                    }
                    session.execute(text(insert_sql), param_dict)
                session.commit()
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
