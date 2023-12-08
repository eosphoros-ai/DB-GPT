from typing import Iterable, Optional, Any
from sqlalchemy import text
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote
from dbgpt.datasource.rdbms.base import RDBMSDatabase


class PostgreSQLDatabase(RDBMSDatabase):
    driver = "postgresql+psycopg2"
    db_type = "postgresql"
    db_dialect = "postgresql"

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
    ) -> RDBMSDatabase:
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )
        return cls.from_uri(db_url, engine_args, **kwargs)

    def _sync_tables_from_db(self) -> Iterable[str]:
        table_results = self.session.execute(
            text(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema'"
            )
        )
        view_results = self.session.execute(
            text(
                "SELECT viewname FROM pg_catalog.pg_views WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema'"
            )
        )
        table_results = set(row[0] for row in table_results)
        view_results = set(row[0] for row in view_results)
        self._all_tables = table_results.union(view_results)
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def get_grants(self):
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"""
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
                    "SELECT datcollate AS collation FROM pg_database WHERE datname = current_database();"
                )
            )
            collation = cursor.fetchone()[0]
            return collation
        except Exception as e:
            print("postgresql get collation error: ", e)
            return None

    def get_users(self):
        """Get user info."""
        try:
            cursor = self.session.execute(
                text("SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%';")
            )
            users = cursor.fetchall()
            return [user[0] for user in users]
        except Exception as e:
            print("postgresql get users error: ", e)
            return []

    def get_fields(self, table_name):
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"SELECT column_name, data_type, column_default, is_nullable, column_name as column_comment \
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
                "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = current_database();"
            )
        )
        character_set = cursor.fetchone()[0]
        return character_set

    def get_show_create_table(self, table_name):
        cur = self.session.execute(
            text(
                f"""
            SELECT a.attname as column_name, pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
            FROM pg_catalog.pg_attribute a
            WHERE a.attnum > 0 AND NOT a.attisdropped AND a.attnum <= (
                SELECT max(a.attnum)
                FROM pg_catalog.pg_attribute a
                WHERE a.attrelid = (SELECT oid FROM pg_catalog.pg_class WHERE relname='{table_name}')
            ) AND a.attrelid = (SELECT oid FROM pg_catalog.pg_class WHERE relname='{table_name}')
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
        tablses = self.table_simple_info()
        comments = []
        for table in tablses:
            table_name = table[0]
            table_comment = self.get_show_create_table(table_name)
            comments.append((table_name, table_comment))
        return comments

    def get_database_list(self):
        session = self._db_sessions()
        cursor = session.execute(text("SELECT datname FROM pg_database;"))
        results = cursor.fetchall()
        return [
            d[0] for d in results if d[0] not in ["template0", "template1", "postgres"]
        ]

    def get_database_names(self):
        session = self._db_sessions()
        cursor = session.execute(text("SELECT datname FROM pg_database;"))
        results = cursor.fetchall()
        return [
            d[0] for d in results if d[0] not in ["template0", "template1", "postgres"]
        ]

    def get_current_db_name(self) -> str:
        return self.session.execute(text("SELECT current_database()")).scalar()

    def table_simple_info(self):
        _sql = f"""
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

    def get_fields(self, table_name, schema_name="public"):
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"""
                SELECT c.column_name, c.data_type, c.column_default, c.is_nullable, d.description
                FROM information_schema.columns c
                LEFT JOIN pg_catalog.pg_description d
                ON (c.table_schema || '.' || c.table_name)::regclass::oid = d.objoid AND c.ordinal_position = d.objsubid
                WHERE c.table_name='{table_name}' AND c.table_schema='{schema_name}'
                """
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"SELECT indexname, indexdef FROM pg_indexes WHERE tablename = '{table_name}'"
            )
        )
        indexes = cursor.fetchall()
        return [(index[0], index[1]) for index in indexes]
