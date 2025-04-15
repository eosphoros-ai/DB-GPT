"""Oracle connector."""

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
        "Enterprise-grade relational database management system with high performance "
        "and scalability."
    ),
)
@dataclass
class OracleParameters(RDBMSDatasourceParameters):
    """Oracle connection parameters."""

    __type__ = "oracle"

    driver: str = field(
        default="oracle+cx_oracle",  # 默认使用 cx_Oracle 驱动
        metadata={
            "help": _("Driver name for Oracle, default is oracle+cx_oracle."),
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
            "help": _("Oracle System ID (SID)."),
        },
    )

    def db_url(self, ssl: bool = False, charset: Optional[str] = None) -> str:
        """Override to generate Oracle-specific db_url."""
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
    """Oracle connector."""

    db_type: str = "oracle"
    db_dialect: str = "oracle"
    driver: str = "oracle+cx_oracle"

    default_db = ["SYS", "SYSTEM", "PDB$SEED"]

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
        """Oracle 的 URI 构建不依赖 db_name，而是用 SID 或 service_name."""
        if not sid and not service_name:
            raise ValueError("Must provide either sid or service_name")

        if service_name:
            dsn = (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})"
                f"(PORT={port}))(CONNECT_DATA=(SERVICE_NAME={service_name})))"
            )
        else:
            dsn = (
                f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})"
                f"(PORT={port}))(CONNECT_DATA=(SID={sid})))"
            )

        bm_pwd = quote_plus(pwd)  # 防止 URL 拼接时错误
        db_url = f"{cls.driver}://{user}:{bm_pwd}@{dsn}"

        return cls.from_uri(db_url, engine_args=engine_args, **kwargs)

    # ✅ 重写 get_fields
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

    # ✅ 重写 get_charset
    def get_charset(self) -> str:
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT VALUE FROM NLS_DATABASE_PARAMETERS "
                    "WHERE PARAMETER = 'NLS_CHARACTERSET'"
                )
            )
            return cursor.fetchone()[0]

    # ✅ 重写 get_grants
    def get_grants(self):
        """Get grant info."""
        with self.session_scope() as session:
            cursor = session.execute(text("SELECT privilege FROM user_sys_privs"))
            grants = cursor.fetchall()
            return grants

    # ✅ 重写 get_users
    def get_users(self) -> List[Tuple[str, None]]:
        with self.session_scope() as session:
            cursor = session.execute(text("SELECT username FROM all_users"))
            return [(row[0], None) for row in cursor.fetchall()]

    # ✅ 重写 get_database_names（PDB 列表）
    def get_database_names(self) -> List[str]:
        with self.session_scope() as session:
            is_cdb = session.execute(text("SELECT CDB FROM V$DATABASE")).fetchone()[0]
            if is_cdb == "YES":
                pdbs = session.execute(
                    text("SELECT NAME FROM V$PDBS WHERE OPEN_MODE = 'READ WRITE'")
                ).fetchall()
                return [name[0] for name in pdbs]
            else:
                # 非CDB架构，返回当前PDB名
                return [
                    session.execute(
                        text("SELECT sys_context('USERENV', 'CON_NAME') FROM dual")
                    ).fetchone()[0]
                ]

    # ✅ 重写 get_table_comments
    def get_table_comments(self, db_name: str) -> List[Tuple[str, str]]:
        with self.session_scope() as session:
            result = session.execute(
                text("SELECT table_name, comments FROM user_tab_comments")
            )
            return [(row[0], row[1]) for row in result.fetchall()]

    # ✅ 重写 get_table_comment
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

    # ✅ 重写 get_column_comments
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
        """Get collation (Oracle: NLS_SORT)."""
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT value FROM NLS_DATABASE_PARAMETERS "
                    "WHERE parameter = 'NLS_SORT'"
                )
            )
            return cursor.fetchone()[0]
