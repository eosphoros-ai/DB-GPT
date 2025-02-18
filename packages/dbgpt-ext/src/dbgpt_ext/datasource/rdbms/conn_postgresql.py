"""PostgreSQL connector."""

import logging
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

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("PostreSQL datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Powerful open-source relational database with extensibility and SQL standards."
    ),
)
@dataclass
class PostgreSQLParameters(RDBMSDatasourceParameters):
    """PostgreSQL connection parameters."""

    __type__ = "postgresql"
    schema: str = field(
        default="public", metadata={"help": _("Database schema, defaults to 'public'")}
    )
    driver: str = field(
        default="postgresql+psycopg2",
        metadata={
            "help": _("Driver name for postgres, default is postgresql+psycopg2."),
        },
    )

    def create_connector(self) -> "PostgreSQLConnector":
        """Create PostgreSQL connector."""
        return PostgreSQLConnector.from_parameters(self)


class PostgreSQLConnector(RDBMSConnector):
    """PostgreSQL connector."""

    driver = "postgresql+psycopg2"
    db_type = "postgresql"
    db_dialect = "postgresql"

    @classmethod
    def param_class(cls) -> Type[PostgreSQLParameters]:
        """Return the parameter class."""
        return PostgreSQLParameters

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
    ) -> "PostgreSQLConnector":
        """Create a new PostgreSQLConnector from host, port, user, pwd, db_name."""
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )
        return cast(PostgreSQLConnector, cls.from_uri(db_url, engine_args, **kwargs))

    @classmethod
    def from_parameters(cls, parameters: PostgreSQLParameters) -> "RDBMSConnector":
        """Create a new connector from parameters."""
        return cls.from_uri_db(
            parameters.host,
            parameters.port,
            parameters.user,
            parameters.password,
            parameters.database,
            schema=parameters.schema,
            engine_args=parameters.engine_args(),
        )

    def _sync_tables_from_db(self) -> Iterable[str]:
        """Read table information from database with schema support."""
        schema = self._schema or "public"

        with self.session_scope() as session:
            # Get tables for specific schema
            table_results = session.execute(
                text(
                    """
                    SELECT tablename 
                    FROM pg_catalog.pg_tables 
                    WHERE schemaname = :schema
                    """
                ),
                {"schema": schema},
            )

            # Get views for specific schema
            view_results = session.execute(
                text(
                    """
                    SELECT viewname 
                    FROM pg_catalog.pg_views 
                    WHERE schemaname = :schema
                    """
                ),
                {"schema": schema},
            )

            table_results = set(row[0] for row in table_results)
            view_results = set(row[0] for row in view_results)
            self._all_tables = table_results.union(view_results)

            # Reflect with schema
            self._metadata.reflect(bind=self._engine, schema=schema)
            return self._all_tables

    def get_grants(self):
        """Get grants."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    """
                    SELECT DISTINCT grantee, privilege_type
                    FROM information_schema.role_table_grants
                    WHERE grantee = CURRENT_USER;"""
                )
            )
            grants = cursor.fetchall()
            return grants

    def get_collation(self):
        """Get collation."""
        try:
            with self.session_scope() as session:
                cursor = session.execute(
                    text(
                        "SELECT datcollate AS collation FROM pg_database WHERE "
                        "datname = current_database();"
                    )
                )
                collation = cursor.fetchone()[0]
                return collation
        except Exception as e:
            logger.warning(f"postgresql get collation error: {str(e)}")
            return None

    def get_users(self):
        """Get user info."""
        try:
            with self.session_scope() as session:
                cursor = session.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%';")
                )
                users = cursor.fetchall()
                return [user[0] for user in users]
        except Exception as e:
            logger.warning(f"postgresql get users error: {str(e)}")
            return []

    def get_fields(self, table_name: str, db_name: Optional[str] = None) -> List[Tuple]:
        """Get column fields about specified table."""
        schema = self._schema or "public"
        sql = """
            SELECT 
                column_name, 
                data_type, 
                column_default, 
                is_nullable,
                col_description(
                    (quote_ident(:schema) || '.' || quote_ident(:table))::regclass::oid,
                    ordinal_position
                ) as column_comment
            FROM information_schema.columns 
            WHERE table_schema = :schema 
            AND table_name = :table
            ORDER BY ordinal_position
        """
        with self.session_scope() as session:
            cursor = session.execute(
                text(sql),
                {"schema": schema, "table": table_name},
            )
            fields = cursor.fetchall()
            return [
                (field[0], field[1], field[2], field[3], field[4]) for field in fields
            ]

    def get_charset(self):
        """Get character_set."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE "
                    "datname = current_database();"
                )
            )
            character_set = cursor.fetchone()[0]
            return character_set

    def get_show_create_table(self, table_name: str) -> str:
        """Return show create table with schema support."""
        schema = self._schema or "public"

        with self.session_scope() as session:
            # Get column definitions
            cur = session.execute(
                text(
                    """
                    SELECT 
                        column_name,
                        data_type,
                        column_default,
                        is_nullable,
                        character_maximum_length,
                        numeric_precision,
                        numeric_scale
                    FROM information_schema.columns
                    WHERE table_schema = :schema 
                    AND table_name = :table
                    ORDER BY ordinal_position
                    """
                ),
                {"schema": schema, "table": table_name},
            )

            create_table = f"CREATE TABLE {schema}.{table_name} (\n"
            for row in cur.fetchall():
                col_name = row[0]
                data_type = row[1]
                default = f"DEFAULT {row[2]}" if row[2] else ""
                nullable = "NOT NULL" if row[3] == "NO" else ""

                # Add length/precision/scale if applicable
                if row[4]:  # character_maximum_length
                    data_type = f"{data_type}({row[4]})"
                elif row[5]:  # numeric_precision
                    if row[6]:  # numeric_scale
                        data_type = f"{data_type}({row[5]},{row[6]})"
                    else:
                        data_type = f"{data_type}({row[5]})"

                create_table += f"    {col_name} {data_type} {default} {nullable},\n"

            create_table = create_table.rstrip(",\n") + "\n)"
            return create_table

    def get_table_comments(self, db_name=None):
        """Get table comments."""
        tablses = self.table_simple_info()
        comments = []
        for table in tablses:
            table_name = table[0]
            table_comment = self.get_show_create_table(table_name)
            comments.append((table_name, table_comment))
        return comments

    def get_database_names(self):
        """Get database names."""
        with self.session_scope() as session:
            cursor = session.execute(text("SELECT datname FROM pg_database;"))
            results = cursor.fetchall()
            return [
                d[0]
                for d in results
                if d[0] not in ["template0", "template1", "postgres"]
            ]

    def get_current_db_name(self) -> str:
        """Get current database name."""
        with self.session_scope() as session:
            return session.execute(text("SELECT current_database()")).scalar()

    def table_simple_info(self):
        """Get table simple info."""
        _sql = """
            SELECT table_name, string_agg(column_name, ', ') AS schema_info
            FROM (
                SELECT c.relname AS table_name, a.attname AS column_name
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
                WHERE c.relkind = 'r'
                AND a.attnum > 0
                AND NOT a.attisdropped
                AND n.nspname NOT LIKE 'pg_%'
                AND n.nspname != 'information_schema'
                ORDER BY c.relname, a.attnum
            ) sub
            GROUP BY table_name;
            """
        with self.session_scope() as session:
            cursor = session.execute(text(_sql))
            results = cursor.fetchall()
            results_str = []
            for result in results:
                results_str.append((str(result[0]), str(result[1])))
            return results_str

    def get_fields_wit_schema(self, table_name, schema_name="public"):
        """Get column fields about specified table."""
        query_sql = f"""
            SELECT c.column_name, c.data_type, c.column_default, c.is_nullable,
             d.description FROM information_schema.columns c
             LEFT JOIN pg_catalog.pg_description d
            ON (c.table_schema || '.' || c.table_name)::regclass::oid = d.objoid
             AND c.ordinal_position = d.objsubid
             WHERE c.table_name='{table_name}' AND c.table_schema='{schema_name}'
        """
        with self.session_scope() as session:
            cursor = session.execute(text(query_sql))
            fields = cursor.fetchall()
            return [
                (field[0], field[1], field[2], field[3], field[4]) for field in fields
            ]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"SELECT indexname, indexdef FROM pg_indexes WHERE "
                    f"tablename = '{table_name}'"
                )
            )
            indexes = cursor.fetchall()
            return [(index[0], index[1]) for index in indexes]
