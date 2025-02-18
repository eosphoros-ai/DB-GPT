"""MSSQL connector."""

from dataclasses import dataclass, field
from typing import Iterable, Type

from sqlalchemy import text

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.rdbms.base import RDBMSConnector, RDBMSDatasourceParameters
from dbgpt.util.i18n_utils import _


@auto_register_resource(
    label=_("MSSQL datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Powerful, scalable, secure relational database system by Microsoft."
    ),
)
@dataclass
class MSSQLParameters(RDBMSDatasourceParameters):
    """MSSQL connection parameters."""

    __type__ = "mssql"
    driver: str = field(
        default="mssql+pymssql",
        metadata={
            "help": _("Driver name for MSSQL, default is mssql+pymssql."),
        },
    )

    def create_connector(self) -> "MSSQLConnector":
        """Create MS SQL connector."""
        return MSSQLConnector.from_parameters(self)


class MSSQLConnector(RDBMSConnector):
    """MSSQL connector."""

    db_type: str = "mssql"
    db_dialect: str = "mssql"
    driver: str = "mssql+pymssql"

    default_db = ["master", "model", "msdb", "tempdb", "modeldb", "resource", "sys"]

    @classmethod
    def param_class(cls) -> Type[MSSQLParameters]:
        """Return the parameter class."""
        return MSSQLParameters

    def table_simple_info(self) -> Iterable[str]:
        """Get table simple info."""
        _tables_sql = """
                SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE
                TABLE_TYPE='BASE TABLE'
            """
        with self.session_scope() as session:
            cursor = session.execute(text(_tables_sql))
            tables_results = cursor.fetchall()
            results = []
            for row in tables_results:
                table_name = row[0]
                _sql = f"""
                    SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE
                     TABLE_NAME='{table_name}'
                """
                cursor_colums = session.execute(text(_sql))
                colum_results = cursor_colums.fetchall()
                table_colums = []
                for row_col in colum_results:
                    field_info = list(row_col)
                    table_colums.append(field_info[0])
                results.append(f"{table_name}({','.join(table_colums)});")
            return results
