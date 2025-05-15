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

    def get_users(self):
        with self.session_scope() as session:
            cursor = session.execute(
                text(
                    "SELECT name FROM sys.server_principals "
                    "WHERE type_desc = 'SQL_LOGIN'"
                )
            )
            return [row[0] for row in cursor.fetchall()]

    def get_grants(self):
        with self.session_scope() as session:
            query = """
            SELECT 
                CASE WHEN perm.state <> 'W' THEN perm.state_desc ELSE 'GRANT WITH
                 GRANT OPTION' END AS [Permission],
                perm.permission_name AS [Permission Name],
                CASE 
                    WHEN perm.class = 0 THEN 'SERVER'
                    WHEN perm.class = 1 THEN OBJECT_NAME(perm.major_id)
                    WHEN perm.class = 3 THEN SCHEMA_NAME(perm.major_id) 
                    ELSE CAST(perm.class AS VARCHAR)
                END AS [Securable],
                princ.name AS [Principal]
            FROM 
                sys.server_permissions perm
                JOIN sys.server_principals princ ON perm.grantee_principal_id = 
                princ.principal_id
            """
            cursor = session.execute(text(query))
            return cursor.fetchall()

    def _decode_if_bytes(self, value):
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    def get_charset(self):
        with self.session_scope() as session:
            query = (
                "SELECT DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS DatabaseCollation"
            )
            cursor = session.execute(text(query))
            result = cursor.fetchone()

            if result and result[0]:
                collation = self._decode_if_bytes(result[0])
                parts = collation.split("_")
                if len(parts) >= 2:
                    return parts[1]
                return collation

            return "SQL_Server_Default"

    def get_collation(self):
        with self.session_scope() as session:
            cursor = session.execute(
                text("SELECT SERVERPROPERTY('Collation') AS DatabaseCollation")
            )
            collation = cursor.fetchone()[0]
            return collation

    def get_table_names(self):
        tables = []

        with self.session_scope() as session:
            query = """
            SELECT 
                TABLE_SCHEMA + '.' + TABLE_NAME AS full_table_name
            FROM 
                INFORMATION_SCHEMA.TABLES
            WHERE 
                TABLE_TYPE = 'BASE TABLE'
                AND TABLE_CATALOG = DB_NAME()
            """

            cursor = session.execute(text(query))
            tables = [row[0] for row in cursor.fetchall()]

            if not tables:
                query = """
                SELECT 
                    SCHEMA_NAME(schema_id) + '.' + name AS full_table_name
                FROM 
                    sys.tables
                """
                cursor = session.execute(text(query))
                tables = [row[0] for row in cursor.fetchall()]

            if not tables:
                query = """
                SELECT 
                    name AS table_name
                FROM 
                    sys.tables
                """
                cursor = session.execute(text(query))
                tables = [row[0] for row in cursor.fetchall()]

            return tables

    def get_columns(self, table_name: str):
        if "." in table_name:
            schema_name, pure_table_name = table_name.split(".", 1)
        else:
            schema_name = "dbo"
            pure_table_name = table_name

        with self.session_scope() as session:
            query = """
            SELECT 
                COLUMN_NAME AS name,
                DATA_TYPE AS type,
                CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END AS nullable,
                COLUMN_DEFAULT AS default_value,
                CHARACTER_MAXIMUM_LENGTH AS max_length
            FROM 
                INFORMATION_SCHEMA.COLUMNS
            WHERE 
                TABLE_SCHEMA = :schema
                AND TABLE_NAME = :table
            ORDER BY 
                ORDINAL_POSITION
            """
            cursor = session.execute(
                text(query), {"schema": schema_name, "table": pure_table_name}
            )
            results = cursor.fetchall()

            columns = []
            for row in results:
                name = row[0].decode("utf-8") if isinstance(row[0], bytes) else row[0]
                col_type = (
                    row[1].decode("utf-8") if isinstance(row[1], bytes) else row[1]
                )
                column = {
                    "name": name,
                    "type": col_type,
                    "nullable": bool(row[2]),
                }

                if row[3] is not None:
                    default = (
                        row[3].decode("utf-8") if isinstance(row[3], bytes) else row[3]
                    )
                    column["default"] = default

                if row[4] is not None:
                    column["max_length"] = row[4]
                columns.append(column)

            return columns

    def get_indexes(self, table_name: str):
        if "." in table_name:
            schema_name, pure_table_name = table_name.split(".", 1)
        else:
            schema_name = "dbo"
            pure_table_name = table_name

        with self.session_scope() as session:
            query = """
            SELECT
                i.name AS index_name,
                c.name AS column_name,
                i.is_unique AS is_unique,
                i.is_primary_key AS is_primary_key
            FROM
                sys.indexes i
            INNER JOIN
                sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id 
                = ic.index_id
            INNER JOIN
                sys.columns c ON ic.object_id = c.object_id AND ic.column_id 
                = c.column_id
            INNER JOIN
                sys.tables t ON i.object_id = t.object_id
            INNER JOIN
                sys.schemas s ON t.schema_id = s.schema_id
            WHERE
                t.name = :table
                AND s.name = :schema
                AND i.name IS NOT NULL
            ORDER BY
                i.name, ic.key_ordinal
            """
            cursor = session.execute(
                text(query), {"schema": schema_name, "table": pure_table_name}
            )
            results = cursor.fetchall()

            index_dict = {}
            for row in results:
                index_name = (
                    row[0].decode("utf-8") if isinstance(row[0], bytes) else row[0]
                )
                column_name = (
                    row[1].decode("utf-8") if isinstance(row[1], bytes) else row[1]
                )
                is_unique = bool(row[2])
                is_primary_key = bool(row[3])
                if index_name not in index_dict:
                    index_dict[index_name] = {
                        "name": index_name,
                        "column_names": [],
                        "unique": is_unique,
                        "primary": is_primary_key,
                    }

                index_dict[index_name]["column_names"].append(column_name)

            return list(index_dict.values())
