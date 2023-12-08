from typing import Iterable, Optional, Any
from sqlalchemy import text
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.datasource.rdbms.dialect.starrocks.sqlalchemy import *


class StarRocksConnect(RDBMSDatabase):
    driver = "starrocks"
    db_type = "starrocks"
    db_dialect = "starrocks"

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
        db_name = self.get_current_db_name()
        table_results = self.session.execute(
            text(
                f'SELECT TABLE_NAME FROM information_schema.tables where TABLE_SCHEMA="{db_name}"'
            )
        )
        # view_results = self.session.execute(text(f'SELECT TABLE_NAME from information_schema.materialized_views where TABLE_SCHEMA="{db_name}"'))
        table_results = set(row[0] for row in table_results)
        # view_results = set(row[0] for row in view_results)
        self._all_tables = table_results
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def get_grants(self):
        session = self._db_sessions()
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
        """Get database current version"""
        return int(self.session.execute(text("select current_version()")).scalar())

    def get_collation(self):
        """Get collation."""
        # StarRocks 排序是表级别的
        return None

    def get_users(self):
        """Get user info."""
        return []

    def get_fields(self, table_name, db_name="database()"):
        """Get column fields about specified table."""
        session = self._db_sessions()
        if db_name != "database()":
            db_name = f'"{db_name}"'
        cursor = session.execute(
            text(
                f'select COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_COMMENT from information_schema.columns where TABLE_NAME="{table_name}" and TABLE_SCHEMA = {db_name}'
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_charset(self):
        """Get character_set."""

        return "utf-8"

    def get_show_create_table(self, table_name):
        # cur = self.session.execute(
        #     text(
        #         f"""show create table {table_name}"""
        #     )
        # )
        # rows = cur.fetchone()
        # create_sql = rows[0]

        # return create_sql
        # 这里是要表描述, 返回建表语句会导致token过长而失败
        cur = self.session.execute(
            text(
                f'SELECT TABLE_COMMENT FROM information_schema.tables where TABLE_NAME="{table_name}" and TABLE_SCHEMA=database()'
            )
        )
        table = cur.fetchone()
        if table:
            return str(table[0])
        else:
            return ""

    def get_table_comments(self, db_name=None):
        if not db_name:
            db_name = self.get_current_db_name()
        cur = self.session.execute(
            text(
                f'SELECT TABLE_NAME,TABLE_COMMENT FROM information_schema.tables where TABLE_SCHEMA="{db_name}"'
            )
        )
        tables = cur.fetchall()
        return [(table[0], table[1]) for table in tables]

    def get_database_list(self):
        return self.get_database_names()

    def get_database_names(self):
        session = self._db_sessions()
        cursor = session.execute(text("SHOW DATABASES;"))
        results = cursor.fetchall()
        return [
            d[0]
            for d in results
            if d[0] not in ["information_schema", "sys", "_statistics_", "dataease"]
        ]

    def get_current_db_name(self) -> str:
        return self.session.execute(text("select database()")).scalar()

    def table_simple_info(self):
        _sql = f"""
          SELECT concat(TABLE_NAME,"(",group_concat(COLUMN_NAME,","),");") FROM information_schema.columns where TABLE_SCHEMA=database() 
            GROUP BY TABLE_NAME
            """
        cursor = self.session.execute(text(_sql))
        results = cursor.fetchall()
        return [x[0] for x in results]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW INDEX FROM {table_name}"))
        indexes = cursor.fetchall()
        return [(index[2], index[4]) for index in indexes]
