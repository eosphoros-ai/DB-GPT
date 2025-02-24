"""Vertica connector."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from sqlalchemy import text
from sqlalchemy.dialects import registry

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)
registry.register(
    "vertica.vertica_python",
    "dbgpt_ext.datasource.rdbms.dialect.vertica.dialect_vertica_python",
    "VerticaDialect",
)


@auto_register_resource(
    label=_("Vertica datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Vertica is a strongly consistent, ACID-compliant, SQL data warehouse, built "
        "for the scale and complexity of today`s data-driven world."
    ),
)
@dataclass
class VerticaParameters(RDBMSDatasourceParameters):
    """Vertica connection parameters."""

    __type__ = "vertica"
    driver: str = field(
        default="vertica+vertica_python",
        metadata={
            "help": _("Driver name for vertica, default is vertica+vertica_python")
        },
    )

    def create_connector(self) -> "VerticaConnector":
        """Create vertica connector"""
        return VerticaConnector.from_parameters(self)


class VerticaConnector(RDBMSConnector):
    """Vertica connector."""

    driver = "vertica+vertica_python"
    db_type = "vertica"
    db_dialect = "vertica"

    @classmethod
    def param_class(cls) -> Type[VerticaParameters]:
        """Return the parameter class."""
        return VerticaParameters

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
    ) -> "VerticaConnector":
        """Create a new VerticaConnector from host, port, user, pwd, db_name."""
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )
        return cast(VerticaConnector, cls.from_uri(db_url, engine_args, **kwargs))

    @property
    def dialect(self) -> str:
        """Return string representation of dialect to use."""
        # inject instruction to prompt according to {dialect} in prompt template.
        return "Vertica sql, \
correct postgresql sql is the another option \
if you don't know much about Vertica. \
尤其要注意，表名称前面一定要带上模式名称！! \
Note， the most important requirement is that \
table name should keep its schema name in "

    def _sync_tables_from_db(self) -> Iterable[str]:
        with self.session_scope() as session:
            table_results = session.execute(
                text(
                    """
                    SELECT table_schema||'.'||table_name
                    FROM v_catalog.tables
                    WHERE table_schema NOT LIKE 'v\_%'
                    UNION
                    SELECT table_schema||'.'||table_name
                    FROM v_catalog.views
                    WHERE table_schema NOT LIKE 'v\_%';
                    """
                )
            )
            self._all_tables = {row[0] for row in table_results}
            self._metadata.reflect(bind=self._engine)
            return self._all_tables

    def get_grants(self):
        """Get grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return None

    def get_users(self):
        """Get user info."""
        try:
            with self.session_scope() as session:
                cursor = session.execute(text("SELECT name FROM v_internal.vs_users;"))
                users = cursor.fetchall()
                return [user[0] for user in users]
        except Exception as e:
            logger.warning(f"vertica get users error: {str(e)}")
            return []

    def get_fields(self, table_name, db_name=None) -> List[Tuple]:
        """Get column fields about specified table."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"""
                    SELECT column_name, data_type, column_default, is_nullable,
                      nvl(comment, column_name) as column_comment
                    FROM v_catalog.columns c
                      LEFT JOIN v_internal.vs_sub_comments s ON c.table_id = s.objectoid
                        AND c.column_name = s.childobject
                    WHERE table_schema||'.'||table_name = '{table_name}';
                    """
                )
            )
            fields = cursor.fetchall()
            return [
                (field[0], field[1], field[2], field[3], field[4]) for field in fields
            ]

    def get_columns(self, table_name: str) -> List[Dict]:
        """Get columns about specified table.

        Args:
            table_name (str): table name

        Returns:
            columns: List[Dict], which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg:[{'name': 'id', 'type': 'int', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        sql = f"""
                SELECT c.column_name, data_type, column_default
                  , (p.column_name IS NOT NULL) is_in_primary_key
                  , nvl(comment, c.column_name) as column_comment
                FROM v_catalog.columns c
                  LEFT JOIN v_internal.vs_sub_comments s ON c.table_id = s.objectoid
                    AND c.column_name = s.childobject
                  LEFT JOIN v_catalog.primary_keys p ON c.table_schema = p.table_schema
                    AND c.table_name = p.table_name
                    AND c.column_name = p.column_name
                WHERE c.table_schema||'.'||c.table_name = '{table_name}';
        """
        with self.session_scope() as session:
            cursor = session.execute(text(sql))
            fields = cursor.fetchall()
            return [
                {
                    "name": field[0],
                    "type": field[1],
                    "default_expression": field[2],
                    "is_in_primary_key": field[3],
                    "comment": field[4],
                }
                for field in fields
            ]

    def get_charset(self):
        """Get character_set."""
        return "utf-8"

    def get_show_create_table(self, table_name: str):
        """Return show create table."""
        with self.session_scope() as session:
            cur = session.execute(
                text(
                    f"""
                    SELECT column_name, data_type
                    FROM v_catalog.columns
                    WHERE table_schema||'.'||table_name = '{table_name}';
                    """
                )
            )
            rows = cur.fetchall()

            create_table_query = f"CREATE TABLE {table_name} (\n"
            for row in rows:
                create_table_query += f"    {row[0]} {row[1]},\n"
            create_table_query = create_table_query.rstrip(",\n") + "\n)"

            return create_table_query

    def get_table_comments(self, db_name=None):
        """Return table comments."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"""
                    SELECT table_schema||'.'||table_name
                      , nvl(comment, table_name) as column_comment
                    FROM v_catalog.tables t
                      LEFT JOIN v_internal.vs_comments c ON t.table_id = c.objectoid
                    WHERE table_schema = '{db_name}'
                    """
                )
            )
            table_comments = cursor.fetchall()
            return [
                (table_comment[0], table_comment[1]) for table_comment in table_comments
            ]

    def get_table_comment(self, table_name: str) -> Dict:
        """Get table comments.

        Args:
            table_name (str): table name
        Returns:
            comment: Dict, which contains text: Optional[str], eg:["text": "comment"]
        """
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"""
                    SELECT nvl(comment, table_name) as column_comment
                    FROM v_catalog.tables t
                      LEFT JOIN v_internal.vs_comments c ON t.table_id = c.objectoid
                    WHERE table_schema||'.'||table_nam e= '{table_name}'
                    """
                )
            )
            return {"text": cursor.scalar()}

    def get_column_comments(self, db_name: str, table_name: str):
        """Return column comments."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"""
                    SELECT column_name, nvl(comment, column_name) as column_comment
                    FROM v_catalog.columns c
                      LEFT JOIN v_internal.vs_sub_comments s ON c.table_id = s.objectoid
                        AND c.column_name = s.childobject
                    WHERE table_schema = '{db_name}' AND table_name = '{table_name}'
                    """
                )
            )
            column_comments = cursor.fetchall()
            return [
                (column_comment[0], column_comment[1])
                for column_comment in column_comments
            ]

    def get_database_names(self):
        """Get database names."""
        with self.session_scope() as session:
            cursor = session.execute(
                text("SELECT schema_name FROM v_catalog.schemata;")
            )
            results = cursor.fetchall()
            return [d[0] for d in results if not d[0].startswith("v_")]

    def get_current_db_name(self) -> str:
        """Get current database name."""
        with self.session_scope() as session:
            return session.execute(text("SELECT current_schema()")).scalar()

    def table_simple_info(self):
        """Get table simple info."""
        _sql = """
            SELECT table_schema||'.'||table_name
              , listagg(column_name using parameters max_length=65000)
            FROM v_catalog.columns
            WHERE table_schema NOT LIKE 'v\_%'
            GROUP BY 1;
            """
        with self.session_scope() as session:
            cursor = session.execute(text(_sql))
            results = cursor.fetchall()
            return results

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        return []
