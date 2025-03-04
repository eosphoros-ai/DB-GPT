"""Clickhouse connector."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

import sqlparse
from sqlalchemy import MetaData, text

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.util.i18n_utils import _
from dbgpt_ext.datasource.schema import DBType

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("Clickhouse datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Columnar database for high-performance analytics and real-time queries."
    ),
)
@dataclass
class ClickhouseParameters(BaseDatasourceParameters):
    """Clickhouse connection parameters."""

    __type__ = "clickhouse"

    host: str = field(metadata={"help": _("Database host, e.g., localhost")})
    port: int = field(metadata={"help": _("Database port, e.g., 8123")})
    user: str = field(metadata={"help": _("Database user to connect")})
    database: str = field(metadata={"help": _("Database name")})
    engine: str = field(
        default="MergeTree", metadata={"help": _("Storage engine, e.g., MergeTree")}
    )
    password: str = field(
        default="${env:DBGPT_DB_PASSWORD}",
        metadata={
            "help": _(
                "Database password, you can write your password directly, of course, "
                "you can also use environment variables, such as "
                "${env:DBGPT_DB_PASSWORD}"
            ),
            "tags": "privacy",
        },
    )
    http_pool_maxsize: int = field(
        default=16, metadata={"help": _("http pool maxsize")}
    )
    http_pool_num_pools: int = field(
        default=12, metadata={"help": _("http pool num_pools")}
    )
    connect_timeout: int = field(
        default=15, metadata={"help": _("Database connect timeout, default 15s")}
    )
    distributed_ddl_task_timeout: int = field(
        default=300, metadata={"help": _("Distributed ddl task timeout, default 300s")}
    )

    def create_connector(self) -> "ClickhouseConnector":
        """Create clickhouse connector."""
        return ClickhouseConnector.from_parameters(self)

    def db_url(self, ssl=False, charset=None):
        raise NotImplementedError("Clickhouse does not support db_url")


class ClickhouseConnector(RDBMSConnector):
    """Clickhouse connector."""

    """db type"""
    db_type: str = "clickhouse"
    """db driver"""
    driver: str = "clickhouse"
    """db dialect"""
    db_dialect: str = "clickhouse"

    client: Any = None

    def __init__(self, client, engine, **kwargs):
        """Create a new ClickhouseConnector from client."""
        self.client = client

        self._all_tables = set()
        self.view_support = False
        self._usable_tables = set()
        self._include_tables = set()
        self._ignore_tables = set()
        self._custom_table_info = set()
        self._indexes_in_table_info = set()
        self._usable_tables = set()
        self._usable_tables = set()
        self._sample_rows_in_table_info = set()

        self._metadata = MetaData()

    @classmethod
    def param_class(cls) -> Type[ClickhouseParameters]:
        """Return the parameter class."""
        return ClickhouseParameters

    @classmethod
    def from_parameters(cls, parameters: ClickhouseParameters) -> "ClickhouseConnector":
        """Create a new ClickhouseConnector from parameters."""
        return cls.from_uri_db(
            parameters.host,
            parameters.port,
            parameters.user,
            parameters.password,
            parameters.database,
            parameters.http_pool_maxsize,
            parameters.http_pool_num_pools,
            parameters.connect_timeout,
            parameters.distributed_ddl_task_timeout,
            parameters.engine,
        )

    @classmethod
    def from_uri_db(
        cls,
        host: str,
        port: int,
        user: str,
        pwd: str,
        db_name: str,
        http_pool_maxsize: int = 16,
        http_pool_num_pools: int = 12,
        connect_timeout: int = 15,
        distributed_ddl_task_timeout: int = 300,
        engine: str = "MergeTree",
        **kwargs: Any,
    ) -> "ClickhouseConnector":
        """Create a new ClickhouseConnector from host, port, user, pwd, db_name."""
        import clickhouse_connect
        from clickhouse_connect.driver import httputil

        # Lazy import

        big_pool_mgr = httputil.get_pool_manager(
            maxsize=http_pool_maxsize, num_pools=http_pool_num_pools
        )
        client = clickhouse_connect.get_client(
            host=host,
            user=user,
            password=pwd,
            port=port,
            connect_timeout=connect_timeout,
            database=db_name,
            settings={"distributed_ddl_task_timeout": distributed_ddl_task_timeout},
            pool_mgr=big_pool_mgr,
        )

        cls.client = client
        return cls(client, engine=engine, **kwargs)

    def get_table_names(self):
        """Get all table names."""
        session = self.client

        with session.query_row_block_stream("SHOW TABLES") as stream:
            tables = [row[0] for block in stream for row in block]
            return tables

    def get_indexes(self, table_name: str) -> List[Dict]:
        """Get table indexes about specified table.

        Args:
            table_name (str): table name
        Returns:
            indexes: List[Dict], eg:[{'name': 'idx_key', 'column_names': ['id']}]
        """
        session = self.client

        _query_sql = f"""
                    SELECT name AS table, primary_key, from system.tables where
                     database ='{self.client.database}' and table = '{table_name}'
                """
        with session.query_row_block_stream(_query_sql) as stream:
            indexes = [block for block in stream]  # noqa
            return [
                {"name": "primary_key", "column_names": column_names.split(",")}
                for table, column_names in indexes[0]
            ]

    @property
    def table_info(self) -> str:
        """Get table info."""
        return self.get_table_info()

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get information about specified tables.

        Follows best practices as specified in: Rajkumar et al, 2022
        (https://arxiv.org/abs/2204.00498)

        If `sample_rows_in_table_info`, the specified number of sample rows will be
        appended to each table description. This can increase performance as
        demonstrated in the paper.
        """
        # TODO:
        return ""

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        result = self.client.command(text(f"SHOW CREATE TABLE  {table_name}"))

        ans = result
        ans = re.sub(r"\s*ENGINE\s*=\s*MergeTree\s*", " ", ans, flags=re.IGNORECASE)
        ans = re.sub(
            r"\s*DEFAULT\s*CHARSET\s*=\s*\w+\s*", " ", ans, flags=re.IGNORECASE
        )
        ans = re.sub(r"\s*SETTINGS\s*\s*\w+\s*", " ", ans, flags=re.IGNORECASE)
        return ans

    def get_columns(self, table_name: str) -> List[Dict]:
        """Get columns.

        Args:
            table_name (str): str
        Returns:
            List[Dict], which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg:[{'name': 'id', 'type': 'UInt64', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        fields = self.get_fields(table_name)
        return [
            {"name": name, "comment": comment, "type": column_type}
            for name, column_type, _, _, comment in fields[0]
        ]

    @property
    def dialect(self) -> str:
        """Return string representation of dialect to use."""
        return ""

    def get_fields(self, table_name, db_name=None) -> List[Tuple]:
        """Get column fields about specified table."""
        session = self.client
        _query_sql = f"""
            SELECT name, type, default_expression, is_in_primary_key, comment
                from system.columns where table='{table_name}'
        """.format(table_name)
        if db_name is not None:
            _query_sql += f" AND database='{db_name}'"
        with session.query_row_block_stream(_query_sql) as stream:
            fields = [block for block in stream]  # noqa
            return fields

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
        """Get character_set."""
        return "UTF-8"

    def get_database_names(self):
        """Get database names."""
        session = self.client

        with session.command("SHOW DATABASES") as stream:
            databases = [
                row[0]
                for block in stream
                for row in block
                if row[0]
                not in ("INFORMATION_SCHEMA", "system", "default", "information_schema")
            ]
            return databases

    def run(self, command: str, fetch: str = "all") -> List:
        """Execute sql command."""
        # TODO need to be implemented
        logger.info("SQL:" + command)
        if not command or len(command) < 0:
            return []
        _, ttype, sql_type, table_name = self.__sql_parse(command)
        if ttype == sqlparse.tokens.DML:
            if sql_type == "SELECT":
                return self._query(command, fetch)
            else:
                self._write(command)
                select_sql = self.convert_sql_write_to_select(command)
                logger.info(f"write result query:{select_sql}")
                return self._query(select_sql)
        else:
            logger.info(
                "DDL execution determines whether to enable through configuration "
            )

            cursor = self.client.command(command)

            if cursor.written_rows:
                result = cursor.result_rows
                field_names = result.column_names

                result = list(result)
                result.insert(0, field_names)
                logger.info("DDL Result:" + str(result))
                if not result:
                    # return self._query(f"SHOW COLUMNS FROM {table_name}")
                    return self.get_simple_fields(table_name)
                return result
            else:
                return self.get_simple_fields(table_name)

    def get_simple_fields(self, table_name):
        """Get column fields about specified table."""
        return self._query(f"SHOW COLUMNS FROM {table_name}")

    def get_current_db_name(self):
        """Get current database name."""
        return self.client.database

    def get_table_comments(self, db_name: str):
        """Get table comments."""
        session = self.client

        _query_sql = f"""
                SELECT table, comment FROM system.tables WHERE database = '{db_name}'
            """.format(db_name)

        with session.query_row_block_stream(_query_sql) as stream:
            table_comments = [row for block in stream for row in block]
            return table_comments

    def get_table_comment(self, table_name: str) -> Dict:
        """Get table comment.

        Args:
            table_name (str): table name
        Returns:
            comment: Dict, which contains text: Optional[str], eg:["text": "comment"]
        """
        session = self.client

        _query_sql = f"""
                SELECT table, comment FROM system.tables WHERE
                 database = '{self.client.database}'and table = '{table_name}'
                 """.format(self.client.database)

        with session.query_row_block_stream(_query_sql) as stream:
            table_comments = [row for block in stream for row in block]
            return [{"text": comment} for table_name, comment in table_comments][0]

    def get_column_comments(self, db_name, table_name):
        """Get column comments."""
        session = self.client
        _query_sql = f"""
            select name column, comment from  system.columns where database='{db_name}'
             and table='{table_name}'
        """.format(db_name, table_name)

        with session.query_row_block_stream(_query_sql) as stream:
            column_comments = [row for block in stream for row in block]
            return column_comments

    def table_simple_info(self):
        """Get table simple info."""
        # group_concat() not supported in clickhouse, use arrayStringConcat+groupArray
        # instead; and quotes need to be escaped

        _sql = f"""
            SELECT concat(TABLE_NAME, '(', arrayStringConcat(
                groupArray(column_name), '-'), ')') AS schema_info
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = '{self.get_current_db_name()}'
            GROUP BY TABLE_NAME
        """
        with self.client.query_row_block_stream(_sql) as stream:
            return [row[0] for block in stream for row in block]

    def _write(self, write_sql: str):
        """Execute write sql.

        Args:
            write_sql (str): sql string
        """
        # TODO need to be implemented
        logger.info(f"Write[{write_sql}]")
        result = self.client.command(write_sql)
        logger.info(f"SQL[{write_sql}], result:{result.written_rows}")

    def _query(self, query: str, fetch: str = "all"):
        """Query data from clickhouse.

        Args:
            query (str): sql string
            fetch (str, optional): "one" or "all". Defaults to "all".

        Raises:
            ValueError: Error

        Returns:
            _type_: List<Result>
        """
        # TODO need to be implemented
        logger.info(f"Query[{query}]")

        if not query:
            return []

        cursor = self.client.query(query)
        if fetch == "all":
            result = cursor.result_rows
        elif fetch == "one":
            result = cursor.first_row
        else:
            raise ValueError("Fetch parameter must be either 'one' or 'all'")

        field_names = cursor.column_names
        result.insert(0, field_names)
        return result

    def __sql_parse(self, sql):
        sql = sql.strip()
        parsed = sqlparse.parse(sql)[0]
        sql_type = parsed.get_type()
        if sql_type == "CREATE":
            table_name = self._extract_table_name_from_ddl(parsed)
        else:
            table_name = parsed.get_name()

        first_token = parsed.token_first(skip_ws=True, skip_cm=False)
        ttype = first_token.ttype
        logger.info(
            f"SQL:{sql}, ttype:{ttype}, sql_type:{sql_type}, table:{table_name}"
        )
        return parsed, ttype, sql_type, table_name

    def _sync_tables_from_db(self) -> Iterable[str]:
        """Read table information from database."""
        # TODO Use a background thread to refresh periodically

        # SQL will raise error with schema
        _schema = (
            None if self.db_type == DBType.SQLite.value() else self._engine.url.database
        )
        # including view support by adding the views as well as tables to the all
        # tables list if view_support is True
        self._all_tables = set(
            self._inspector.get_table_names(schema=_schema)
            + (
                self._inspector.get_view_names(schema=_schema)
                if self.view_support
                else []
            )
        )
        return self._all_tables

    def close(self):
        """Close the connection.

        TODO: implement this method
        """
        pass
