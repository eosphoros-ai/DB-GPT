"""MSSQL connector."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type
import logging

logger = logging.getLogger(__name__)

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
        results = []
        for table_name in self.get_table_names():
            columns = self.get_columns(table_name)
            table_colums = []
            for col in columns:
                if col.get("comment"):
                    table_colums.append(f"{col['name']}({col['comment']})")
                else:
                    table_colums.append(col['name'])

            table_str = f"{table_name}({','.join(table_colums)})"
            table_comment = self.get_table_comment(table_name)
            if table_comment.get("text"):
                table_str += f" COMMENT[{table_comment['text']}]"
            results.append(f"{table_str};")
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
                c.COLUMN_NAME AS name,
                c.DATA_TYPE AS type,
                CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END AS nullable,
                c.COLUMN_DEFAULT AS default_value,
                c.CHARACTER_MAXIMUM_LENGTH AS max_length,
                p.value AS comment
            FROM 
                INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN sys.extended_properties p ON 
                p.major_id = OBJECT_ID(QUOTENAME(c.TABLE_SCHEMA) + '.' + QUOTENAME(c.TABLE_NAME))  
                AND p.minor_id = (
                    SELECT column_id 
                    FROM sys.columns 
                    WHERE name = c.COLUMN_NAME 
                    AND object_id = OBJECT_ID(QUOTENAME(c.TABLE_SCHEMA) + '.' + QUOTENAME(c.TABLE_NAME))
                )
                AND p.name = 'MS_Description'
                AND p.class = 1 
            WHERE 
                c.TABLE_SCHEMA = :schema
                AND c.TABLE_NAME = :table
            ORDER BY 
                c.ORDINAL_POSITION
            """
            cursor = session.execute(
                text(query), {"schema": schema_name, "table": pure_table_name}
            )
            results = cursor.fetchall()

            columns = []
            for row in results:
                name = self._decode_if_bytes(row[0])
                col_type = self._decode_if_bytes(row[1])
                column = {
                    "name": name,
                    "type": col_type,
                    "nullable": bool(row[2]),
                }

                if row[3] is not None:
                    default = self._decode_if_bytes(row[3])
                    column["default"] = default

                if row[4] is not None:
                    column["max_length"] = row[4]

                if len(row) > 5 and row[5] is not None:
                    comment = self._decode_if_bytes(row[5])
                    column["comment"] = comment
                columns.append(column)

            return columns

    def get_table_comment(self, table_name: str) -> Dict[str, Optional[str]]:
        """Get table comment.

        Args:
            table_name (str): table name

        Returns:
            Dict[str, Optional[str]]: dict with key 'text'
        """
        if "." in table_name:
            schema_name, pure_table_name = table_name.split(".", 1)
        else:
            schema_name = "dbo"
            pure_table_name = table_name

        with self.session_scope() as session:
            query = """
            SELECT 
                value 
            FROM 
                sys.extended_properties 
            WHERE 
                major_id = OBJECT_ID(:schema_dot_table) 
                AND minor_id = 0 
                AND name = 'MS_Description'
            """
            full_table_name = f"{schema_name}.{pure_table_name}"
            try:
                cursor = session.execute(
                    text(query), {"schema_dot_table": full_table_name}
                )
                result = cursor.fetchone()

                if result and result[0]:
                    comment = self._decode_if_bytes(result[0])
                    return {"text": comment}
            except Exception:
                pass
            return {"text": None}

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

    def _transform_val(self, val):
        if isinstance(val, str):
            try:
                return val.encode("latin-1").decode("gbk")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        return val

    def _query(self, query: str, fetch: str = "all"):
        result = super()._query(query, fetch)
        if not result or not isinstance(result, list) or len(result) < 2:
            return result

        # Result[0] is headers
        # Rest are rows
        new_rows = []
        for row in result[1:]:
            new_row = [self._transform_val(val) for val in row]
            new_rows.append(tuple(new_row))

        # Reassemble
        return [result[0]] + new_rows

    def query_ex(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        fetch: str = "all",
        timeout: Optional[float] = None,
    ) -> Tuple[List[str], Optional[List]]:
        field_names, results = super().query_ex(query, params, fetch, timeout)

        if not results:
            return field_names, results

        new_results = []
        for row in results:
            new_row = [self._transform_val(val) for val in row]
            new_results.append(tuple(new_row))

        return field_names, new_results
