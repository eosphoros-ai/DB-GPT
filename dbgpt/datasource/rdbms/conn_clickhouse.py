import re
from typing import Optional, Any
from sqlalchemy import text
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from dbgpt.datasource.rdbms.base import RDBMSDatabase


class ClickhouseConnect(RDBMSDatabase):
    """Connect Clickhouse Database fetch MetaData
    Args:
    Usage:
    """

    """db type"""
    db_type: str = "clickhouse"
    """db driver"""
    driver: str = "clickhouse"
    """db dialect"""
    db_dialect: str = "clickhouse"

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

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        return ""

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW CREATE TABLE  {table_name}"))
        ans = cursor.fetchall()
        ans = ans[0][0]
        ans = re.sub(r"\s*ENGINE\s*=\s*MergeTree\s*", " ", ans, flags=re.IGNORECASE)
        ans = re.sub(
            r"\s*DEFAULT\s*CHARSET\s*=\s*\w+\s*", " ", ans, flags=re.IGNORECASE
        )
        ans = re.sub(r"\s*SETTINGS\s*\s*\w+\s*", " ", ans, flags=re.IGNORECASE)
        return ans

    def get_fields(self, table_name):
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"SELECT name, type, default_expression, is_in_primary_key, comment  from system.columns where table='{table_name}'".format(
                    table_name
                )
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_users(self):
        return []

    def get_grants(self):
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        return "UTF-8"

    def get_database_list(self):
        return []

    def get_database_names(self):
        return []

    def get_table_comments(self, db_name):
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"""SELECT table, comment FROM system.tables WHERE database = '{db_name}'""".format(
                    db_name
                )
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]

    def table_simple_info(self):
        # group_concat() not supported in clickhouse, use arrayStringConcat+groupArray instead; and quotes need to be escaped
        _sql = f"""
                select concat(TABLE_NAME, \'(\' , arrayStringConcat(groupArray(column_name),\'-\'), \')\') as schema_info 
                from information_schema.COLUMNS where table_schema=\'{self.get_current_db_name()}\' group by TABLE_NAME; """

        cursor = self.session.execute(text(_sql))
        results = cursor.fetchall()
        return results
