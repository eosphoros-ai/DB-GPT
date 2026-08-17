"""StarRocks connector."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from sqlalchemy import text
from sqlalchemy.exc import NoSuchTableError

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _

from .dialect.starrocks.sqlalchemy import *  # noqa

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("StarRocks datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("An Open-Source, High-Performance Analytical Database."),
)
@dataclass
class StarRocksParameters(RDBMSDatasourceParameters):
    """StarRocks connection parameters."""

    __type__ = "starrocks"

    driver: str = field(
        default="starrocks",
        metadata={
            "help": _("Driver name for starrocks, default is starrocks."),
        },
    )

    def create_connector(self) -> "StarRocksConnector":
        """Create StarRocks connector."""
        return StarRocksConnector.from_parameters(self)


class StarRocksConnector(RDBMSConnector):
    """StarRocks connector."""

    _UNSUPPORTED_SAMPLE_TYPES = {"BITMAP", "HLL", "PERCENTILE"}

    driver = "starrocks"
    db_type = "starrocks"
    db_dialect = "starrocks"

    @classmethod
    def param_class(cls) -> Type[StarRocksParameters]:
        """Return the parameter class."""
        return StarRocksParameters

    def _reflect_metadata(self) -> None:
        """Skip eager schema reflection for StarRocks.

        StarRocks exposes all schema information needed by this connector through
        ``information_schema``. Avoiding eager reflection prevents one unsupported or
        concurrently dropped table from making the whole connector unusable.
        """

    @classmethod
    def from_uri_db(
        cls: Type["StarRocksConnector"],
        host: str,
        port: int,
        user: str,
        pwd: str,
        db_name: str,
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> "StarRocksConnector":
        """Create a new StarRocksConnector from host, port, user, pwd, db_name."""
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )
        return cast(StarRocksConnector, cls.from_uri(db_url, engine_args, **kwargs))

    def _sync_tables_from_db(self) -> Iterable[str]:
        db_name = self.get_current_db_name()
        with self.session_scope() as session:
            table_results = session.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.tables "
                    "WHERE TABLE_SCHEMA=:db_name"
                ),
                {"db_name": db_name},
            )
            # view_results = session.execute(text(f'SELECT TABLE_NAME from
            # information_schema.materialized_views where TABLE_SCHEMA="{db_name}"'))
            table_results = set(row[0] for row in table_results)  # noqa: C401
            # view_results = set(row[0] for row in view_results)
            self._all_tables = table_results
            return self._all_tables

    def get_grants(self):
        """Get grants."""
        with self.session_scope() as session:
            cursor = session.execute(text("SHOW GRANTS"))
            grants = cursor.fetchall()
            if len(grants) == 0:
                return []
            if len(grants[0]) == 2:
                grants_list = [x[1] for x in grants]
            else:
                grants_list = [x[2] for x in grants]
            return grants_list

    def _get_current_version(self):
        """Get database current version."""
        with self.session_scope() as session:
            return int(session.execute(text("select current_version()")).scalar())

    def get_collation(self):
        """Get collation."""
        # StarRocks 排序是表级别的
        return None

    def get_users(self):
        """Get user info."""
        return []

    def get_fields(self, table_name: str, db_name: str = "database()") -> List[Tuple]:
        """Get column fields about specified table."""
        if db_name == "database()":
            db_name = self.get_current_db_name()
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, "
                    "COLUMN_COMMENT FROM information_schema.columns "
                    "WHERE TABLE_NAME=:table_name AND TABLE_SCHEMA=:db_name "
                    "ORDER BY ORDINAL_POSITION"
                ),
                {"table_name": table_name, "db_name": db_name},
            )
            fields = cursor.fetchall()
            return [
                (field[0], field[1], field[2], field[3], field[4]) for field in fields
            ]

    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Return columns without routing through SQLAlchemy metadata reflection."""
        return [
            {
                "name": field[0],
                "type": field[1],
                "default": field[2],
                "nullable": field[3] == "YES",
                "comment": field[4],
            }
            for field in self.get_fields(table_name)
        ]

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get table information directly from ``information_schema``."""
        all_table_names = sorted(self.get_usable_table_names())
        if table_names is not None:
            missing_tables = set(table_names).difference(all_table_names)
            if missing_tables:
                raise ValueError(f"table_names {missing_tables} not found in database")
            all_table_names = table_names

        tables = []
        for table_name in all_table_names:
            if self._custom_table_info and table_name in self._custom_table_info:
                tables.append(self._custom_table_info[table_name])
                continue
            try:
                table_info = self._build_table_info(table_name)
            except Exception as error:
                if self._is_missing_table_error(error):
                    logger.warning(
                        "Skipping StarRocks table %s because it no longer exists",
                        table_name,
                    )
                    continue
                raise
            if table_info:
                tables.append(table_info)
        return "\n\n".join(tables)

    def _build_table_info(self, table_name: str) -> str:
        """Build table information without constructing SQLAlchemy ``Table`` objects."""
        fields = self.get_fields(table_name)
        if not fields:
            logger.warning(
                "Skipping StarRocks table %s because it has no visible columns",
                table_name,
            )
            return ""

        quote_identifier = self._engine.dialect.identifier_preparer.quote_identifier
        column_definitions = []
        for name, column_type, default, nullable, comment in fields:
            definition = f"  {quote_identifier(name)} {column_type}"
            if nullable == "NO":
                definition += " NOT NULL"
            if default is not None:
                definition += f" DEFAULT {default}"
            if comment:
                escaped_comment = str(comment).replace("'", "''")
                definition += f" COMMENT '{escaped_comment}'"
            column_definitions.append(definition)

        quoted_table = quote_identifier(table_name)
        table_info = (
            f"CREATE TABLE {quoted_table} (\n" + ",\n".join(column_definitions) + "\n)"
        )
        if self._sample_rows_in_table_info:
            sample_columns = [
                name
                for name, column_type, *_ in fields
                if self._base_type_name(column_type)
                not in self._UNSUPPORTED_SAMPLE_TYPES
            ]
            table_info += self._get_sample_rows_by_name(table_name, sample_columns)
        if self._indexes_in_table_info:
            table_info += self._get_indexes_info_by_name(table_name)
        return table_info

    @staticmethod
    def _base_type_name(column_type: str) -> str:
        """Return the top-level StarRocks type name."""
        return str(column_type).split("(", 1)[0].split("<", 1)[0].strip().upper()

    def _get_sample_rows_by_name(self, table_name: str, column_names: List[str]) -> str:
        """Return formatted sample rows without requiring reflected metadata."""
        if not column_names:
            return ""
        quote_identifier = self._engine.dialect.identifier_preparer.quote_identifier
        quoted_table = quote_identifier(table_name)
        selected_columns = ", ".join(
            quote_identifier(column_name) for column_name in column_names
        )
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"SELECT {selected_columns} FROM {quoted_table} "
                    f"LIMIT {int(self._sample_rows_in_table_info)}"
                )
            )
            rows = cursor.fetchall()

        columns_str = "\t".join(column_names)
        sample_rows_str = "\n".join(
            "\t".join("NULL" if value is None else str(value)[:100] for value in row)
            for row in rows
        )
        return (
            f"\n\n/*\n{self._sample_rows_in_table_info} rows from "
            f"{table_name} table:\n{columns_str}\n{sample_rows_str}\n*/"
        )

    def _get_indexes_info_by_name(self, table_name: str) -> str:
        """Return formatted index information without reflected metadata."""
        indexes = self.get_indexes(table_name)
        if not indexes:
            return ""
        indexes_str = "\n".join(
            f"Name: {name}, Column: {column}" for name, column in indexes
        )
        return f"\n\n/*\nTable Indexes:\n{indexes_str}\n*/"

    @staticmethod
    def _is_missing_table_error(error: Exception) -> bool:
        """Return whether an exception represents a concurrently removed table."""
        if isinstance(error, NoSuchTableError):
            return True
        original = getattr(error, "orig", error)
        args = getattr(original, "args", ())
        return bool(args and args[0] in (1146, 5502))

    def get_charset(self):
        """Get character_set."""
        return "utf-8"

    def get_show_create_table(self, table_name: str):
        """Get show create table."""
        # cur = self.session.execute(
        #     text(
        #         f"""show create table {table_name}"""
        #     )
        # )
        # rows = cur.fetchone()
        # create_sql = rows[0]

        # return create_sql
        # Here is the table description, returning the create table statement will
        # cause the token to be too long and fail
        with self.session_scope() as session:
            cur = session.execute(
                text(
                    "SELECT TABLE_COMMENT FROM information_schema.tables where "
                    "TABLE_NAME=:table_name and TABLE_SCHEMA=database()"
                ),
                {"table_name": table_name},
            )
            table = cur.fetchone()
            if table:
                return str(table[0])
            else:
                return ""

    def get_table_comments(self, db_name=None):
        """Get table comments."""
        if not db_name:
            db_name = self.get_current_db_name()
        with self.session_scope() as session:
            cur = session.execute(
                text(
                    "SELECT TABLE_NAME,TABLE_COMMENT FROM information_schema.tables "
                    "where TABLE_SCHEMA=:db_name"
                ),
                {"db_name": db_name},
            )
            tables = cur.fetchall()
            return [(table[0], table[1]) for table in tables]

    def get_database_names(self):
        """Get database names."""
        with self.session_scope() as session:
            cursor = session.execute(text("SHOW DATABASES;"))
            results = cursor.fetchall()
            return [
                d[0]
                for d in results
                if d[0] not in ["information_schema", "sys", "_statistics_", "dataease"]
            ]

    def get_current_db_name(self) -> str:
        """Get current database name."""
        with self.session_scope() as session:
            return session.execute(text("select database()")).scalar()

    def table_simple_info(self):
        """Get table simple info."""
        _sql = """
          SELECT concat(TABLE_NAME,"(",group_concat(COLUMN_NAME,","),");")
           FROM information_schema.columns where TABLE_SCHEMA=database()
            GROUP BY TABLE_NAME
        """
        with self.session_scope() as session:
            cursor = session.execute(text(_sql))
            results = cursor.fetchall()
            return [x[0] for x in results]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        quote_identifier = self._engine.dialect.identifier_preparer.quote_identifier
        quoted_table = quote_identifier(table_name)
        try:
            with self.session_scope() as session:
                cursor = session.execute(text(f"SHOW INDEX FROM {quoted_table}"))
                indexes = cursor.fetchall()
                return [(index[2], index[4]) for index in indexes]
        except Exception as error:
            if self._is_missing_table_error(error):
                return []
            raise
