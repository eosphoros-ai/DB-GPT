"""Oracle connector using python-oracledb."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Type
from urllib.parse import quote_plus

from sqlalchemy import text

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _


@auto_register_resource(
    label=_("Oracle datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Enterprise-grade relational database with oracledb driver (python-oracledb)."
    ),
)
@dataclass
class OracleParameters(RDBMSDatasourceParameters):
    """Oracle connection parameters."""

    __type__ = "oracle"

    driver: str = field(
        default="oracle+oracledb",  # ✅ 使用 python-oracledb 驱动
        metadata={
            "help": _("Driver name for Oracle, default is oracle+oracledb."),
        },
    )

    service_name: Optional[str] = field(
        default=None,
        metadata={
            "help": _("Oracle service name (alternative to SID)."),
        },
    )

    sid: Optional[str] = field(
        default=None,
        metadata={
            "help": _("Oracle SID (System ID, alternative to service name)."),
        },
    )

    def db_url(self, ssl: bool = False, charset: Optional[str] = None) -> str:
        if self.service_name:
            dsn = (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={self.host})"
                f"(PORT={self.port}))(CONNECT_DATA=(SERVICE_NAME={self.service_name})))"
            )
        elif self.sid:
            dsn = (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={self.host})"
                f"(PORT={self.port}))(CONNECT_DATA=(SID={self.sid})))"
            )
        else:
            raise ValueError("Either service_name or sid must be provided for Oracle.")

        return f"{self.driver}://{self.user}:{self.password}@{dsn}"

    def create_connector(self) -> "OracleConnector":
        return OracleConnector.from_parameters(self)


class OracleConnector(RDBMSConnector):
    db_type: str = "oracle"
    db_dialect: str = "oracle"
    driver: str = "oracle+oracledb"

    @classmethod
    def param_class(cls) -> Type[RDBMSDatasourceParameters]:
        return OracleParameters

    @classmethod
    def from_uri_db(
        cls,
        host: str,
        port: int,
        user: str,
        pwd: str,
        sid: Optional[str] = None,
        service_name: Optional[str] = None,
        engine_args: Optional[dict] = None,
        **kwargs,
    ) -> "OracleConnector":
        if not sid and not service_name:
            raise ValueError("Must provide either sid or service_name")

        if service_name:
            dsn = (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
                f"(HOST={host})(PORT={port}))(CONNECT_DATA=(SERVICE_NAME={service_name})))"
            )
        else:
            dsn = (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})"
                f"(PORT={port}))(CONNECT_DATA=(SID={sid})))"
            )

        bm_pwd = quote_plus(pwd)
        db_url = f"{cls.driver}://{user}:{bm_pwd}@{dsn}"

        return cls.from_uri(db_url, engine_args=engine_args, **kwargs)

    def get_simple_fields(self, table_name):
        """Get column fields about specified table."""
        return self.get_fields(table_name)

    def get_fields(self, table_name: str, db_name=None) -> List[Tuple]:
        with self.session_scope() as session:
            query = f"""
                SELECT col.column_name,
                       col.data_type,
                       col.data_default,
                       col.nullable,
                       comm.comments
                FROM user_tab_columns col
                LEFT JOIN user_col_comments comm
                ON col.table_name = comm.table_name
                AND col.column_name = comm.column_name
                WHERE col.table_name = '{table_name.upper()}'
            """
            result = session.execute(text(query))
            return result.fetchall()

    def get_charset(self) -> str:
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT VALUE FROM NLS_DATABASE_PARAMETERS "
                    "WHERE PARAMETER = 'NLS_CHARACTERSET'"
                )
            )
            return cursor.fetchone()[0]

    def get_grants(self):
        with self.session_scope() as session:
            cursor = session.execute(text("SELECT privilege FROM user_sys_privs"))
            return cursor.fetchall()

    def get_users(self) -> List[Tuple[str, None]]:
        with self.session_scope() as session:
            cursor = session.execute(text("SELECT username FROM all_users"))
            return [(row[0], None) for row in cursor.fetchall()]

    def get_database_names(self) -> List[str]:
        with self.session_scope() as session:
            is_cdb = session.execute(text("SELECT CDB FROM V$DATABASE")).fetchone()[0]
            if is_cdb == "YES":
                pdbs = session.execute(
                    text("SELECT NAME FROM V$PDBS WHERE OPEN_MODE = 'READ WRITE'")
                ).fetchall()
                return [name[0] for name in pdbs]
            else:
                return [
                    session.execute(
                        text("SELECT sys_context('USERENV', 'CON_NAME') FROM dual")
                    ).fetchone()[0]
                ]

    def get_table_comments(self, db_name: str) -> List[Tuple[str, str]]:
        with self.session_scope() as session:
            result = session.execute(
                text("SELECT table_name, comments FROM user_tab_comments")
            )
            return [(row[0], row[1]) for row in result.fetchall()]

    def get_table_comment(self, table_name: str) -> Dict:
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    f"SELECT comments FROM user_tab_comments "
                    f"WHERE table_name = '{table_name.upper()}'"
                )
            )
            row = cursor.fetchone()
            return {"text": row[0] if row else ""}

    def get_column_comments(
        self, db_name: str, table_name: str
    ) -> List[Tuple[str, str]]:
        with self.session_scope() as session:
            cursor = session.execute(
                text(f"""
                    SELECT column_name, comments
                    FROM user_col_comments
                    WHERE table_name = '{table_name.upper()}'
                """)
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_collation(self) -> str:
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT value FROM NLS_DATABASE_PARAMETERS "
                    "WHERE parameter = 'NLS_SORT'"
                )
            )
            return cursor.fetchone()[0]
