"""Doris connector."""

import weakref
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.orm import scoped_session, sessionmaker

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _


@auto_register_resource(
    label=_("Apache Doris datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("A new-generation open-source real-time data warehouse."),
)
@dataclass
class DorisParameters(RDBMSDatasourceParameters):
    """Doris connection parameters.

    Doris has a same protocol with MySQL, so we suggest to use MySQL connector to
    connect Doris.
    """

    __type__ = "doris"
    driver: str = field(
        default="mysql+pymysql",
        metadata={
            "help": _(
                "Driver name for Doris, default is mysql+pymysql (MySQL compatible)."
            ),
        },
    )

    def create_connector(self) -> "DorisConnector":
        """Create doris connector"""
        return DorisConnector.from_parameters(self)


class DorisConnector(RDBMSConnector):
    """Doris connector."""

    driver = "mysql+pymysql"
    db_type = "doris"
    db_dialect = "mysql"

    def __init__(
        self,
        engine,
        schema: Optional[str] = None,
        metadata: Optional[MetaData] = None,
        ignore_tables: Optional[List[str]] = None,
        include_tables: Optional[List[str]] = None,
        sample_rows_in_table_info: int = 3,
        indexes_in_table_info: bool = False,
        custom_table_info: Optional[Dict[str, str]] = None,
        view_support: bool = False,
    ):
        """Initialize Doris connector without triggering reflection.

        Override parent __init__ to avoid automatic metadata.reflect() call
        which causes issues with Doris data type parsing.
        """
        # Initialize basic attributes (copied from parent but without reflect)
        self._is_closed = False
        self._engine = engine
        self._schema = schema
        if include_tables and ignore_tables:
            raise ValueError("Cannot specify both include_tables and ignore_tables")

        if not custom_table_info:
            custom_table_info = {}

        self._inspector = inspect(engine)
        session_factory = sessionmaker(bind=engine)
        Session_Manages = scoped_session(session_factory)
        self._db_sessions = Session_Manages
        self._sessions = weakref.WeakSet()

        self.view_support = view_support
        self._usable_tables = set()
        self._include_tables = set()
        self._ignore_tables = set()
        self._custom_table_info = custom_table_info
        self._sample_rows_in_table_info = sample_rows_in_table_info
        self._indexes_in_table_info = indexes_in_table_info

        # NOT call reflect() to avoid Doris type parsing issues
        # self._metadata = metadata or MetaData()
        # self._metadata.reflect(bind=self._engine)

        self._all_tables = set(self._sync_tables_from_db())

    @classmethod
    def param_class(cls) -> Type[DorisParameters]:
        """Return the parameter class."""
        return DorisParameters

    @classmethod
    def from_uri_db(
        cls,
        host: str,
        port: int,
        user: str,
        pwd: str,
        db_name: str,
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> "DorisConnector":
        """Create a new DorisConnector from host, port, user, pwd, db_name."""
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )
        return cast(DorisConnector, cls.from_uri(db_url, engine_args, **kwargs))

    def _sync_tables_from_db(self) -> Iterable[str]:
        """Sync tables from db."""
        with self.session_scope() as session:
            table_results = session.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.tables where "
                    "TABLE_SCHEMA=database()"
                )
            )
            table_results = set(row[0] for row in table_results)  # noqa: C401
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
        """Get collation.

        ref `SHOW COLLATION <https://doris.apache.org/zh-CN/docs/dev/sql-manual/
        sql-reference/Show-Statements/SHOW-COLLATION/>`_

        """
        with self.session_scope() as session:
            cursor = session.execute(text("SHOW COLLATION"))
            results = cursor.fetchall()
            return "" if not results else results[0][0]

    def get_users(self):
        """Get user info."""
        return []

    def get_columns(self, table_name: str) -> List[Dict]:
        """Get columns.

        Args:
            table_name (str): str
        Returns:
            columns: List[Dict], which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg:[{'name': 'id', 'type': 'UInt64', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        fields = self.get_fields(table_name)
        return [
            {
                "name": field[0],
                "type": field[1],
                "default": field[2],
                "nullable": field[3],
                "comment": field[4],
            }
            for field in fields
        ]

    def get_fields(self, table_name, db_name=None) -> List[Tuple]:
        """Get column fields about specified table."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "select COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, "
                    "COLUMN_COMMENT from information_schema.columns "
                    f'where TABLE_NAME="{table_name}" and TABLE_SCHEMA=database()'
                )
            )
            fields = cursor.fetchall()
            return [
                (field[0], field[1], field[2], field[3], field[4]) for field in fields
            ]

    def get_charset(self) -> str:
        """Get character_set."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    """
                    SELECT DEFAULT_CHARACTER_SET_NAME 
                    FROM information_schema.SCHEMATA 
                    where SCHEMA_NAME=database() 
                    """
                )
            )
            ans = cursor.fetchall()
            if ans:
                return ans[0][0]
            return ""

    def get_show_create_table(self, table_name) -> str:
        """Get show create table."""
        # cur = self.get_session().execute(
        #     text(
        #         f"""show create table {table_name}"""
        #     )
        # )
        # rows = cur.fetchone()
        # create_sql = rows[1]
        # return create_sql
        # Here is the table description, returning the create table statement will
        with self.session_scope() as session:
            cur = session.execute(
                text(
                    f"SELECT TABLE_COMMENT "
                    f"FROM information_schema.tables "
                    f'where TABLE_NAME="{table_name}" and TABLE_SCHEMA=database()'
                )
            )
            table = cur.fetchone()
            if table:
                return str(table[0])
            else:
                return ""

    def get_table_comments(self, db_name=None):
        """Get table comments."""
        db_name = "database()" if not db_name else f"'{db_name}'"
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"SELECT TABLE_NAME,TABLE_COMMENT "
                    f"FROM information_schema.tables "
                    f"where TABLE_SCHEMA={db_name}"
                )
            )
            tables = cursor.fetchall()
            return [(table[0], table[1]) for table in tables]

    def get_table_comment(self, table_name=None):
        """Get table comment."""
        cursor = self.get_session().execute(
            text(
                f"SELECT TABLE_COMMENT "
                f"FROM information_schema.tables "
                f"where TABLE_NAME={table_name} and TABLE_SCHEMA=database()"
            )
        )
        table_comment = cursor.fetchone()
        if table_comment:
            return {"text": str(table_comment[0])}
        else:
            return {"text": None}

    def get_database_names(self):
        """Get database names."""
        with self.session_scope() as session:
            cursor = session.execute(text("SHOW DATABASES"))
            results = cursor.fetchall()
            return [
                d[0]
                for d in results
                if d[0]
                not in [
                    "information_schema",
                    "sys",
                    "_statistics_",
                    "mysql",
                    "__internal_schema",
                    "doris_audit_db__",
                ]
            ]

    def get_current_db_name(self) -> str:
        """Get current database name."""
        with self.session_scope() as session:
            return session.execute(text("select database()")).scalar()

    def table_simple_info(self):
        """Get table simple info."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT concat(TABLE_NAME,'(',group_concat(COLUMN_NAME,','),');') "
                    "FROM information_schema.columns "
                    "where TABLE_SCHEMA=database() "
                    "GROUP BY TABLE_NAME"
                )
            )
            results = cursor.fetchall()
            return [x[0] for x in results]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        with self.session_scope() as session:
            cursor = session.execute(text(f"SHOW INDEX FROM {table_name}"))
            indexes = cursor.fetchall()
            return [(index[2], index[4]) for index in indexes]

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get information about specified tables.

        Override parent method to avoid dependency on metadata.reflect()
        which causes issues with Doris data type parsing.
        Uses direct SQL queries to get table information.
        """
        all_table_names = list(self.get_usable_table_names())
        if table_names is not None:
            missing_tables = set(table_names).difference(all_table_names)
            if missing_tables:
                raise ValueError(f"table_names {missing_tables} not found in database")
            all_table_names = table_names

        if not all_table_names:
            return ""

        tables = []
        for table_name in all_table_names:
            if self._custom_table_info and table_name in self._custom_table_info:
                tables.append(self._custom_table_info[table_name])
                continue

            # Build table info using direct SQL queries
            table_info = self._build_table_info_for_doris(table_name)
            tables.append(table_info)

        return "\n\n".join(tables)

    def _build_table_info_for_doris(self, table_name: str) -> str:
        """Build table information for Doris using direct SQL queries."""
        try:
            with self.session_scope() as session:
                # Get table structure information
                cursor = session.execute(
                    text(
                        "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, "
                        "COLUMN_DEFAULT, COLUMN_COMMENT "
                        "FROM information_schema.columns "
                        f'WHERE TABLE_NAME="{table_name}" AND TABLE_SCHEMA=database() '
                        "ORDER BY ORDINAL_POSITION"
                    )
                )
                columns = cursor.fetchall()

                if not columns:
                    return f"-- Table {table_name} not found"

                # Build CREATE TABLE statement
                table_info = f"CREATE TABLE {table_name} (\n"
                column_definitions = []

                for col in columns:
                    col_name, col_type, is_nullable, col_default, col_comment = col
                    col_def = f"  `{col_name}` {col_type}"

                    if is_nullable == "NO":
                        col_def += " NOT NULL"

                    if col_default is not None:
                        col_def += f" DEFAULT {col_default}"

                    if col_comment:
                        col_def += f" COMMENT '{col_comment}'"

                    column_definitions.append(col_def)

                table_info += ",\n".join(column_definitions)
                table_info += "\n)"

                # Get table comment if available
                try:
                    comment_cursor = session.execute(
                        text(
                            "SELECT TABLE_COMMENT FROM information_schema.tables "
                            f'WHERE TABLE_NAME="{table_name}"'
                            f" AND TABLE_SCHEMA=database()"
                        )
                    )
                    table_comment = comment_cursor.fetchone()
                    if table_comment and table_comment[0]:
                        table_info += f" COMMENT='{table_comment[0]}'"
                except Exception:
                    pass  # Ignore comment retrieval errors

                # Add sample rows if configured
                if self._sample_rows_in_table_info > 0:
                    table_info += self._get_sample_rows_for_doris(table_name)

                # Add index information if configured
                if self._indexes_in_table_info:
                    table_info += self._get_indexes_info_for_doris(table_name)

                return table_info

        except Exception as e:
            return f"-- Error getting info for table {table_name}: {str(e)}"

    def _get_sample_rows_for_doris(self, table_name: str) -> str:
        """Get sample rows for Doris table."""
        try:
            with self.session_scope() as session:
                cursor = session.execute(
                    text(
                        f"SELECT * FROM {table_name} LIMIT "
                        f"{self._sample_rows_in_table_info}"
                    )
                )
                rows = cursor.fetchall()

                if not rows:
                    return ""

                # Get column names
                column_names = list(cursor.keys())
                columns_str = "\t".join(column_names)

                # Format sample rows
                sample_rows_str = "\n".join(
                    [
                        "\t".join(
                            [
                                str(val)[:100] if val is not None else "NULL"
                                for val in row
                            ]
                        )
                        for row in rows
                    ]
                )

                return (
                    f"\n\n/*\n{self._sample_rows_in_table_info} rows from "
                    f"{table_name} table:\n{columns_str}\n{sample_rows_str}\n*/"
                )

        except Exception:
            return f"\n\n/*\nError getting sample rows for table {table_name}\n*/"

    def _get_indexes_info_for_doris(self, table_name: str) -> str:
        """Get index information for Doris table."""
        try:
            indexes = self.get_indexes(table_name)
            if not indexes:
                return f"\n\n/*\nTable Indexes for {table_name}:\nNo indexes found\n*/"

            indexes_str = "\n".join(
                [f"Index: {idx[0]}, Column: {idx[1]}" for idx in indexes]
            )
            return f"\n\n/*\nTable Indexes for {table_name}:\n{indexes_str}\n*/"

        except Exception:
            return f"\n\n/*\nError getting indexes for table {table_name}\n*/"
