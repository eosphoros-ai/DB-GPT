"""PostgreSQL connector."""
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

import jwt
from langchain.docstore.document import Document
from langchain.document_loaders import CubeSemanticLoader
from sqlalchemy import text

from .base import RDBMSConnector

logger = logging.getLogger(__name__)


class CubeJSConnector(RDBMSConnector):
    """PostgreSQL connector."""

    driver = "postgresql+psycopg2"
    db_type = "cubejs"
    db_dialect = "postgresql"
    CUBE_API_URL = ""
    CUBE_API_SECRET = ""

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
    ) -> "CubeJSConnector":
        """Create a new PostgreSQLConnector from host, port, user, pwd, db_name."""
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )

        if "comment" in kwargs:
            remark_value = kwargs["comment"]
            json_data = json.loads(remark_value)
            cls.CUBE_API_URL = json_data["CUBE_API_URL"]
            cls.CUBE_API_SECRET = json_data["CUBE_API_SECRET"]
        return cast(CubeJSConnector, cls.from_uri(db_url, engine_args))

    def _sync_tables_from_db(self) -> Iterable[str]:
        table_results = self.session.execute(
            text(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE "
                "schemaname != 'pg_catalog' AND schemaname != 'information_schema'"
            )
        )
        view_results = self.session.execute(
            text(
                "SELECT viewname FROM pg_catalog.pg_views WHERE "
                "schemaname != 'pg_catalog' AND schemaname != 'information_schema'"
            )
        )
        table_results = set(row[0] for row in table_results)  # noqa: C401
        view_results = set(row[0] for row in view_results)  # noqa: C401
        self._all_tables = table_results.union(view_results)
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def get_grants(self):
        """Get grants."""
        session = self._db_sessions()
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
            session = self._db_sessions()
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
        documents = self.ingest_cube_meta(table_name)

        return [
            {
                "name": doc.metadata["column_name"],
                "type": doc.metadata["column_data_type"],
                "comment": doc.metadata["column_description"],
            }
            for doc in documents
            if doc.metadata["table_name"] == table_name
        ]

    def get_fields(self, table_name) -> List[Tuple]:
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                "SELECT column_name, data_type, column_default, is_nullable, "
                "column_name as column_comment \
                FROM information_schema.columns WHERE table_name = :table_name",
            ),
            {"table_name": table_name},
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_charset(self):
        """Get character_set."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE "
                "datname = current_database();"
            )
        )
        character_set = cursor.fetchone()[0]
        return character_set

    def get_show_create_table(self, table_name: str):
        """Return show create table."""
        cur = self.session.execute(
            text(
                f"""
            SELECT a.attname as column_name,
             pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
            FROM pg_catalog.pg_attribute a
            WHERE a.attnum > 0 AND NOT a.attisdropped AND a.attnum <= (
                SELECT max(a.attnum)
                FROM pg_catalog.pg_attribute a
                WHERE a.attrelid = (SELECT oid FROM pg_catalog.pg_class
                    WHERE relname='{table_name}')
            ) AND a.attrelid = (SELECT oid FROM pg_catalog.pg_class
                 WHERE relname='{table_name}')
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
        session = self._db_sessions()
        cursor = session.execute(text("SELECT datname FROM pg_database;"))
        results = cursor.fetchall()
        return [
            d[0] for d in results if d[0] not in ["template0", "template1", "postgres"]
        ]

    def get_current_db_name(self) -> str:
        """Get current database name."""
        return self.session.execute(text("SELECT current_database()")).scalar()

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
        cursor = self.session.execute(text(_sql))
        results = cursor.fetchall()
        return results

    def get_fields_wit_schema(self, table_name, schema_name="public"):
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"""
                SELECT c.column_name, c.data_type, c.column_default, c.is_nullable,
                 d.description FROM information_schema.columns c
                 LEFT JOIN pg_catalog.pg_description d
                ON (c.table_schema || '.' || c.table_name)::regclass::oid = d.objoid
                 AND c.ordinal_position = d.objsubid
                 WHERE c.table_name='{table_name}' AND c.table_schema='{schema_name}'
                """
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        return []

    def ingest_cube_meta(self, table_name) -> List[Document]:
        security_context: dict[str, Any] = {}
        token = jwt.encode(security_context, self.CUBE_API_SECRET, algorithm="HS256")

        loader = CubeSemanticLoader(self.CUBE_API_URL, token)
        documents = loader.load()
        return documents
