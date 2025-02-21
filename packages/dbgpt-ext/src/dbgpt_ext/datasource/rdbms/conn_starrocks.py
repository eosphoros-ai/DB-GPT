"""StarRocks connector."""

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Tuple, Type, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from sqlalchemy import text

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _

from .dialect.starrocks.sqlalchemy import *  # noqa


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

    driver = "starrocks"
    db_type = "starrocks"
    db_dialect = "starrocks"

    @classmethod
    def param_class(cls) -> Type[StarRocksParameters]:
        """Return the parameter class."""
        return StarRocksParameters

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
                    "SELECT TABLE_NAME FROM information_schema.tables where "
                    f'TABLE_SCHEMA="{db_name}"'
                )
            )
            # view_results = session.execute(text(f'SELECT TABLE_NAME from
            # information_schema.materialized_views where TABLE_SCHEMA="{db_name}"'))
            table_results = set(row[0] for row in table_results)  # noqa: C401
            # view_results = set(row[0] for row in view_results)
            self._all_tables = table_results
            self._metadata.reflect(bind=self._engine)
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

    def get_fields(self, table_name, db_name="database()") -> List[Tuple]:
        """Get column fields about specified table."""
        with self.session_scope() as session:
            if db_name != "database()":
                db_name = f'"{db_name}"'
            cursor = session.execute(
                text(
                    "select COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, "
                    "COLUMN_COMMENT from information_schema.columns where "
                    f'TABLE_NAME="{table_name}" and TABLE_SCHEMA = {db_name}'
                )
            )
            fields = cursor.fetchall()
            return [
                (field[0], field[1], field[2], field[3], field[4]) for field in fields
            ]

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
                    f'TABLE_NAME="{table_name}" and TABLE_SCHEMA=database()'
                )
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
                    f'where TABLE_SCHEMA="{db_name}"'
                )
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
        with self.session_scope() as session:
            cursor = session.execute(text(f"SHOW INDEX FROM {table_name}"))
            indexes = cursor.fetchall()
            return [(index[2], index[4]) for index in indexes]
