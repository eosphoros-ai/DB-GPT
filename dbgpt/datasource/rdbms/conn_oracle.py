"""Oracle connector."""

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

import sqlparse
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import column, table, text

from .base import RDBMSConnector

logger = logging.getLogger(__name__)


def _remove_trailing_semicolon(sql: str) -> str:
    """Remove trailing semicolon if present."""
    return sql.rstrip(';')


class OracleConnector(RDBMSConnector):
    """
    Oracle connector.
    Oracle Database 12.1 (or later) is required.
    """

    driver = "oracle+oracledb"
    db_type = "oracle"
    db_dialect = "oracle"

    def __init__(self, engine: Engine, *args, **kwargs):
        """Initialize Oracle connector with SQLAlchemy engine."""
        super().__init__(engine, *args, **kwargs)

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
    ) -> "OracleConnector":
        """Create a new OracleConnector from host, port, user, pwd, db_name."""
        db_url = f"{cls.driver}://{user}:{pwd}@{host}:{port}/{db_name}"
        return cast(OracleConnector, cls.from_uri(db_url, engine_args, **kwargs))

    def _sync_tables_from_db(self) -> Iterable[str]:
        """Synchronize tables from the database."""
        table_results = self.session.execute(
            text("SELECT table_name FROM all_tables WHERE owner = USER")
        )
        view_results = self.session.execute(
            text("SELECT view_name FROM all_views WHERE owner = USER")
        )
        table_results = set(row[0] for row in table_results)  # noqa: F541
        view_results = set(row[0] for row in view_results)  # noqa: F541
        self._all_tables = table_results.union(view_results)
        self._metadata.reflect(bind=self._engine)
        return self._all_tables

    def get_current_db_name(self) -> str:
        """Get current Oracle schema name instead of database name."""
        return self.session.execute(text("SELECT USER FROM DUAL")).scalar()

    def table_simple_info(self):
        """Return table simple info for Oracle."""
        _sql = """
            SELECT table_name, column_name 
            FROM all_tab_columns
            WHERE owner = USER
        """
        cursor = self.session.execute(text(_sql))
        results = cursor.fetchall()
        return results

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get information about specified tables for Oracle.

        Follows best practices and adapts to Oracle specifics, ensuring case-insensitive comparison
        and handling of table names.
        """
        inspector = inspect(self._engine)
        all_table_names = {name.upper() for name in self.get_usable_table_names()}

        if table_names is not None:
            missing_tables = set(list(name.upper() for name in table_names)).difference(
                all_table_names
            )
            if missing_tables:
                raise ValueError(
                    f"Specified table_names {missing_tables} not found in the database."
                )
            all_table_names = set(name.upper() for name in table_names)

        tables_info = []
        for table_name in all_table_names:
            # Fetching table metadata and constructing a string representation
            columns_info = inspector.get_columns(table_name)
            column_defs = ",\n".join(
                f"{col['name']} {col['type']}" for col in columns_info
            )
            create_table_desc = f"CREATE TABLE {table_name} (\n{column_defs}\n);"

            table_info = create_table_desc

            if self._indexes_in_table_info:
                # Fetching index information
                index_info = self._get_table_indexes(table_name)
                table_info += f"\n\n-- Indexes:\n{index_info}"

            if self._sample_rows_in_table_info:
                # Fetching sample rows
                sample_rows = self._get_sample_rows(table_name)
                table_info += f"\n\n-- Sample Rows:\n{sample_rows}"

            tables_info.append(table_info)

        return "\n\n".join(tables_info)

    def _get_table_indexes(self, table: Table) -> str:
        """Get table indexes for an Oracle table."""
        try:
            indexes = self._inspector.get_indexes(table.name)
            indexes_formatted = [
                {"name": idx["name"], "column_names": idx["column_names"]}
                for idx in indexes
            ]
            return f"Table Indexes:\n{indexes_formatted}"
        except SQLAlchemyError as e:
            logger.error(f"Error fetching indexes: {e}")
            return "[]"

    def _get_sample_rows(self, table_name: str) -> str:
        """
        Fetches sample rows from the specified Oracle table in a compatible manner.
        Pitfall 1: The FETCH FIRST syntax is valid in Oracle 12c and later versions, while ROWNUM works in all versions of Oracle.
        Pitfall 2: In some cases, Oracle might not accept a semicolon at the end of a query statement.
        """
        # First, retrieve the table metadata to get column names
        table_obj = Table(table_name, MetaData(), autoload_with=self._engine)
        columns_str = "\t".join([col.name for col in table_obj.columns])

        sample_query = text(
            f"SELECT * FROM {table_name} WHERE ROWNUM <= {self._sample_rows_in_table_info}"
        )

        try:
            with self._engine.connect() as conn:
                sample_rows_result = conn.execute(sample_query)
                sample_rows = sample_rows_result.fetchall()

                # Format each row as a tab-separated string, limiting string lengths
                sample_rows_str_list = [
                    "\t".join(str(cell)[:100] for cell in row) for row in sample_rows
                ]
                sample_rows_str = "\n".join(sample_rows_str_list)

        except SQLAlchemyError as e:
            logger.error(f"Error fetching sample rows: {e}")
            return "Error fetching sample rows."

        return (
            f"{self._sample_rows_in_table_info} rows from {table_name} table:\n"
            f"{columns_str}\n"
            f"{sample_rows_str}"
        )

    def get_columns(self, table_name: str) -> List[Dict]:
        """Get columns about specified Oracle table."""

        # Fetch basic column information using Inspector
        columns_info = self._inspector.get_columns(table_name)

        # Fetch primary key columns
        primary_key_info = self._inspector.get_pk_constraint(table_name)
        primary_key_columns = primary_key_info["constrained_columns"]

        # If primary_key_columns is not a list, convert it to a list
        if not isinstance(primary_key_columns, list):
            primary_key_columns = [primary_key_columns]

        # Enhance column information with additional details
        enhanced_columns = []
        for col in columns_info:
            # Check if the column is in primary key
            is_in_primary_key = col["name"] in primary_key_columns

            # Construct the column info dict
            column_info = {
                "name": col["name"],
                "type": str(col["type"]),  # convert SQLAlchemy type to string
                "default_expression": (
                    str(col["default"]) if col["default"] is not None else None
                ),
                "is_in_primary_key": is_in_primary_key,
                "comment": col["comment"] if col["comment"] is not None else None,
            }
            enhanced_columns.append(column_info)

        return enhanced_columns

    def convert_sql_write_to_select(self, write_sql: str) -> str:
        """Convert SQL write command to a SELECT command for Oracle."""
        # Placeholder for Oracle-specific conversion logic
        return f"SELECT * FROM ({write_sql}) WHERE 1=0"

    def get_table_comment(self, table_name: str) -> Dict:
        """Get table comments for an Oracle table.

        Args:
            table_name (str): table name
        Returns:
            comment: Dict, which contains text: Optional[str], eg:["text": "comment"]
        """
        try:
            result = self.session.execute(
                text("SELECT comments FROM user_tab_comments WHERE table_name = :table_name"),
                {"table_name": table_name}
            ).fetchone()
            return {"text": result[0]} if result else {"text": None}
        except SQLAlchemyError as e:
            logger.error(f"Error getting table comment: {e}")
            return {"text": None}

    def get_grants(self):
        """Get grant info for Oracle."""
        session = self._db_sessions()
        grants = []

        return grants

    def get_charset(self) -> str:
        """Get character set."""
        session = self._db_sessions()
        charset_query = text(
            "SELECT value FROM NLS_DATABASE_PARAMETERS WHERE parameter = 'NLS_CHARACTERSET'"
        )
        character_set = session.execute(charset_query).scalar()
        return character_set

    def get_collation(self) -> str | None:
        """
        Get collation for Oracle. Note: Oracle does not support collations in the same way as other DBMSs like MySQL or SQL Server.
        This method returns None to indicate that collation querying is not applicable.
        """
        logger.warning(
            "Collation querying is not applicable in Oracle as it does not support database-level collations."
        )
        return None

    def _write(self, write_sql: str):
        """Run a SQL write command and return the results as a list of tuples.

        Args:
            write_sql (str): SQL write command to run
        """
        logger.info(f"Write[{write_sql}]")
        command = _remove_trailing_semicolon(write_sql)
        return super()._write(command)

    def _query(self, query: str, fetch: str = "all"):
        """Run a SQL query and return the results as a list of tuples.

        Args:
            query (str): SQL query to run
            fetch (str): fetch type
        """
        logger.info(f"Query[{query}]")
        query = _remove_trailing_semicolon(query)
        return super()._query(query, fetch)

    def run(self, command: str, fetch: str = "all") -> List:
        """Execute a SQL command and return a string representing the results."""
        logger.info("SQL:" + command)
        command = _remove_trailing_semicolon(command)
        return super().run(command, fetch)

