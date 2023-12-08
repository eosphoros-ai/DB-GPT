from typing import Iterable, Optional, Any
from sqlalchemy import text
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote
from dbgpt.datasource.rdbms.base import RDBMSDatabase


class DorisConnect(RDBMSDatabase):
    driver = "doris"
    db_type = "doris"
    db_dialect = "doris"

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
        table_results = self.get_session().execute(
            text(
                f"SELECT TABLE_NAME FROM information_schema.tables where TABLE_SCHEMA=database()"
            )
        )
        table_results = set(row[0] for row in table_results)
        self._all_tables = table_results
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def get_grants(self):
        cursor = self.get_session().execute(text("SHOW GRANTS"))
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
        return int(
            self.get_session().execute(text("select current_version()")).scalar()
        )

    def get_collation(self):
        """Get collation.
        ref: https://doris.apache.org/zh-CN/docs/dev/sql-manual/sql-reference/Show-Statements/SHOW-COLLATION/
        """
        cursor = self.get_session().execute(text("SHOW COLLATION"))
        results = cursor.fetchall()
        return "" if not results else results[0][0]

    def get_users(self):
        """Get user info."""
        return []

    def get_fields(self, table_name):
        """Get column fields about specified table."""
        cursor = self.get_session().execute(
            text(
                f"select COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_COMMENT "
                f"from information_schema.columns "
                f'where TABLE_NAME="{table_name}" and TABLE_SCHEMA=database()'
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_charset(self):
        """Get character_set."""
        return "utf-8"

    def get_show_create_table(self, table_name):
        # cur = self.get_session().execute(
        #     text(
        #         f"""show create table {table_name}"""
        #     )
        # )
        # rows = cur.fetchone()
        # create_sql = rows[1]
        # return create_sql
        # 这里是要表描述, 返回建表语句会导致token过长而失败
        cur = self.get_session().execute(
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
        db_name = "database()" if not db_name else f"'{db_name}'"
        cursor = self.get_session().execute(
            text(
                f"SELECT TABLE_NAME,TABLE_COMMENT "
                f"FROM information_schema.tables "
                f"where TABLE_SCHEMA={db_name}"
            )
        )
        tables = cursor.fetchall()
        return [(table[0], table[1]) for table in tables]

    def get_database_list(self):
        return self.get_database_names()

    def get_database_names(self):
        cursor = self.get_session().execute(text("SHOW DATABASES"))
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
        return self.get_session().execute(text("select database()")).scalar()

    def table_simple_info(self):
        cursor = self.get_session().execute(
            text(
                f"SELECT concat(TABLE_NAME,'(',group_concat(COLUMN_NAME,','),');') "
                f"FROM information_schema.columns "
                f"where TABLE_SCHEMA=database() "
                f"GROUP BY TABLE_NAME"
            )
        )
        results = cursor.fetchall()
        return [x[0] for x in results]

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        cursor = self.get_session().execute(text(f"SHOW INDEX FROM {table_name}"))
        indexes = cursor.fetchall()
        return [(index[2], index[4]) for index in indexes]
