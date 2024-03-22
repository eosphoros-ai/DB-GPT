"""Base class for RDBMS connectors."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

import sqlalchemy
import sqlparse
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.schema import CreateTable

from dbgpt.datasource.base import BaseConnector
from dbgpt.storage.schema import DBType

logger = logging.getLogger(__name__)


def _format_index(index: sqlalchemy.engine.interfaces.ReflectedIndex) -> str:
    return (
        f'Name: {index["name"]}, Unique: {index["unique"]},'
        f' Columns: {str(index["column_names"])}'
    )


class RDBMSConnector(BaseConnector):
    """SQLAlchemy wrapper around a database."""

    def __init__(
        self,
        engine,
        schema: Optional[str] = None,
        metadata: Optional[MetaData] = None,
        ignore_tables: Optional[List[str]] = None,
        include_tables: Optional[List[str]] = None,
        sample_rows_in_table_info: int = 3,
        indexes_in_table_info: bool = False,
        custom_table_info: Optional[Dict[str, str]] = None,
        view_support: bool = False,
    ):
        """Create engine from database URI.

        Args:
           - engine: Engine sqlalchemy.engine
           - schema: Optional[str].
           - metadata: Optional[MetaData]
           - ignore_tables: Optional[List[str]]
           - include_tables: Optional[List[str]]
           - sample_rows_in_table_info: int default:3,
           - indexes_in_table_info: bool = False,
           - custom_table_info: Optional[dict] = None,
           - view_support: bool = False,
        """
        self._engine = engine
        self._schema = schema
        if include_tables and ignore_tables:
            raise ValueError("Cannot specify both include_tables and ignore_tables")

        if not custom_table_info:
            custom_table_info = {}

        self._inspector = inspect(engine)
        session_factory = sessionmaker(bind=engine)
        Session_Manages = scoped_session(session_factory)
        self._db_sessions = Session_Manages
        self.session = self.get_session()

        self.view_support = view_support
        self._usable_tables: Set[str] = set()
        self._include_tables: Set[str] = set()
        self._ignore_tables: Set[str] = set()
        self._custom_table_info = custom_table_info
        self._sample_rows_in_table_info = sample_rows_in_table_info
        self._indexes_in_table_info = indexes_in_table_info

        self._metadata = metadata or MetaData()
        self._metadata.reflect(bind=self._engine)

        self._all_tables: Set[str] = cast(Set[str], self._sync_tables_from_db())

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
    ) -> RDBMSConnector:
        """Construct a SQLAlchemy engine from uri database.

        Args:
            host (str): database host.
            port (int): database port.
            user (str): database user.
            pwd (str): database password.
            db_name (str): database name.
            engine_args (Optional[dict]):other engine_args.
        """
        db_url: str = (
            f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        )
        return cls.from_uri(db_url, engine_args, **kwargs)

    @classmethod
    def from_uri(
        cls, database_uri: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSConnector:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine(database_uri, **_engine_args), **kwargs)

    @property
    def dialect(self) -> str:
        """Return string representation of dialect to use."""
        return self._engine.dialect.name

    def _sync_tables_from_db(self) -> Iterable[str]:
        """Read table information from database."""
        # TODO Use a background thread to refresh periodically

        # SQL will raise error with schema
        _schema = (
            None if self.db_type == DBType.SQLite.value() else self._engine.url.database
        )
        # including view support by adding the views as well as tables to the all
        # tables list if view_support is True
        self._all_tables = set(
            self._inspector.get_table_names(schema=_schema)
            + (
                self._inspector.get_view_names(schema=_schema)
                if self.view_support
                else []
            )
        )
        return self._all_tables

    def get_usable_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        if self._include_tables:
            return self._include_tables
        return self._all_tables - self._ignore_tables

    def get_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        return self.get_usable_table_names()

    def get_session(self):
        """Get session."""
        session = self._db_sessions()

        return session

    def get_current_db_name(self) -> str:
        """Get current database name.

        Returns:
            str: database name
        """
        return self.session.execute(text("SELECT DATABASE()")).scalar()

    def table_simple_info(self):
        """Return table simple info."""
        _sql = f"""
                select concat(table_name, "(" , group_concat(column_name), ")")
                as schema_info from information_schema.COLUMNS where
                table_schema="{self.get_current_db_name()}" group by TABLE_NAME;
            """
        cursor = self.session.execute(text(_sql))
        results = cursor.fetchall()
        return results

    @property
    def table_info(self) -> str:
        """Information about all tables in the database."""
        return self.get_table_info()

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get information about specified tables.

        Follows best practices as specified in: Rajkumar et al, 2022
        (https://arxiv.org/abs/2204.00498)

        If `sample_rows_in_table_info`, the specified number of sample rows will be
        appended to each table description. This can increase performance as
        demonstrated in the paper.
        """
        all_table_names = self.get_usable_table_names()
        if table_names is not None:
            missing_tables = set(table_names).difference(all_table_names)
            if missing_tables:
                raise ValueError(f"table_names {missing_tables} not found in database")
            all_table_names = table_names

        meta_tables = [
            tbl
            for tbl in self._metadata.sorted_tables
            if tbl.name in set(all_table_names)
            and not (self.dialect == "sqlite" and tbl.name.startswith("sqlite_"))
        ]

        tables = []
        for table in meta_tables:
            if self._custom_table_info and table.name in self._custom_table_info:
                tables.append(self._custom_table_info[table.name])
                continue

            # add create table command
            create_table = str(CreateTable(table).compile(self._engine))
            table_info = f"{create_table.rstrip()}"
            has_extra_info = (
                self._indexes_in_table_info or self._sample_rows_in_table_info
            )
            if has_extra_info:
                table_info += "\n\n/*"
            if self._indexes_in_table_info:
                table_info += f"\n{self._get_table_indexes(table)}\n"
            if self._sample_rows_in_table_info:
                table_info += f"\n{self._get_sample_rows(table)}\n"
            if has_extra_info:
                table_info += "*/"
            tables.append(table_info)
        final_str = "\n\n".join(tables)
        return final_str

    def get_columns(self, table_name: str) -> List[Dict]:
        """Get columns about specified table.

        Args:
            table_name (str): table name

        Returns:
            columns: List[Dict], which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg:[{'name': 'id', 'type': 'int', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        return self._inspector.get_columns(table_name)

    def _get_sample_rows(self, table: Table) -> str:
        # build the select command
        command = select(table).limit(self._sample_rows_in_table_info)

        # save the columns in string format
        columns_str = "\t".join([col.name for col in table.columns])

        try:
            # get the sample rows
            with self._engine.connect() as connection:
                sample_rows_result: CursorResult = connection.execute(command)
                # shorten values in the sample rows
                sample_rows = list(
                    map(lambda ls: [str(i)[:100] for i in ls], sample_rows_result)
                )

            # save the sample rows in string format
            sample_rows_str = "\n".join(["\t".join(row) for row in sample_rows])

        # in some dialects when there are no rows in the table a
        # 'ProgrammingError' is returned
        except ProgrammingError:
            sample_rows_str = ""

        return (
            f"{self._sample_rows_in_table_info} rows from {table.name} table:\n"
            f"{columns_str}\n"
            f"{sample_rows_str}"
        )

    def _get_table_indexes(self, table: Table) -> str:
        indexes = self._inspector.get_indexes(table.name)
        indexes_formatted = "\n".join(map(_format_index, indexes))
        return f"Table Indexes:\n{indexes_formatted}"

    def get_table_info_no_throw(self, table_names: Optional[List[str]] = None) -> str:
        """Get information about specified tables."""
        try:
            return self.get_table_info(table_names)
        except ValueError as e:
            """Format the error message"""
            return f"Error: {e}"

    def _write(self, write_sql: str):
        """Run a SQL write command and return the results as a list of tuples.

        Args:
            write_sql (str): SQL write command to run
        """
        logger.info(f"Write[{write_sql}]")
        db_cache = self._engine.url.database
        result = self.session.execute(text(write_sql))
        self.session.commit()
        # TODO  Subsequent optimization of dynamically specified database submission
        #  loss target problem
        self.session.execute(text(f"use `{db_cache}`"))
        logger.info(f"SQL[{write_sql}], result:{result.rowcount}")
        return result.rowcount

    def _query(self, query: str, fetch: str = "all"):
        """Run a SQL query and return the results as a list of tuples.

        Args:
            query (str): SQL query to run
            fetch (str): fetch type
        """
        result: List[Any] = []

        logger.info(f"Query[{query}]")
        if not query:
            return result
        cursor = self.session.execute(text(query))
        if cursor.returns_rows:
            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = [cursor.fetchone()]
            else:
                raise ValueError("Fetch parameter must be either 'one' or 'all'")
            field_names = tuple(i[0:] for i in cursor.keys())

            result.insert(0, field_names)
            return result

    def query_table_schema(self, table_name: str):
        """Query table schema.

        Args:
            table_name (str): table name
        """
        sql = f"select * from {table_name} limit 1"
        return self._query(sql)

    def query_ex(self, query: str, fetch: str = "all"):
        """Execute a SQL command and return the results.

        Only for query command.

        Args:
            query (str): SQL query to run
            fetch (str): fetch type

        Returns:
            List: result list
        """
        logger.info(f"Query[{query}]")
        if not query:
            return [], None
        cursor = self.session.execute(text(query))
        if cursor.returns_rows:
            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = cursor.fetchone()  # type: ignore
            else:
                raise ValueError("Fetch parameter must be either 'one' or 'all'")
            field_names = list(cursor.keys())

            result = list(result)
            return field_names, result
        return [], None

    def run(self, command: str, fetch: str = "all") -> List:
        """Execute a SQL command and return a string representing the results."""
        logger.info("SQL:" + command)
        if not command or len(command) < 0:
            return []
        parsed, ttype, sql_type, table_name = self.__sql_parse(command)
        if ttype == sqlparse.tokens.DML:
            if sql_type == "SELECT":
                return self._query(command, fetch)
            else:
                self._write(command)
                select_sql = self.convert_sql_write_to_select(command)
                logger.info(f"write result query:{select_sql}")
                return self._query(select_sql)

        else:
            logger.info(
                "DDL execution determines whether to enable through configuration "
            )
            cursor = self.session.execute(text(command))
            self.session.commit()
            if cursor.returns_rows:
                result = cursor.fetchall()
                field_names = tuple(i[0:] for i in cursor.keys())
                result = list(result)
                result.insert(0, field_names)
                logger.info("DDL Result:" + str(result))
                if not result:
                    # return self._query(f"SHOW COLUMNS FROM {table_name}")
                    return self.get_simple_fields(table_name)
                return result
            else:
                return self.get_simple_fields(table_name)

    def run_to_df(self, command: str, fetch: str = "all"):
        """Execute sql command and return result as dataframe."""
        import pandas as pd

        # Pandas has too much dependence and the import time is too long
        # TODO: Remove the dependency on pandas
        result_lst = self.run(command, fetch)
        colunms = result_lst[0]
        values = result_lst[1:]
        return pd.DataFrame(values, columns=colunms)

    def run_no_throw(self, command: str, fetch: str = "all") -> List:
        """Execute a SQL command and return a string representing the results.

        If the statement returns rows, a string of the results is returned.
        If the statement returns no rows, an empty string is returned.

        If the statement throws an error, the error message is returned.
        """
        try:
            return self.run(command, fetch)
        except SQLAlchemyError as e:
            """Format the error message"""
            logger.warning(f"Run SQL command failed: {e}")
            return []

    def convert_sql_write_to_select(self, write_sql: str) -> str:
        """Convert SQL write command to a SELECT command.

        SQL classification processing
        author:xiangh8

        Examples:
            .. code-block:: python

                write_sql = "insert into test(id) values (1)"
                select_sql = convert_sql_write_to_select(write_sql)
                print(select_sql)
                # SELECT * FROM test WHERE id=1
        Args:
            write_sql (str): SQL write command

        Returns:
            str: SELECT command corresponding to the write command
        """
        # Convert the SQL command to lowercase and split by space
        parts = write_sql.lower().split()
        # Get the command type (insert, delete, update)
        cmd_type = parts[0]

        # Handle according to command type
        if cmd_type == "insert":
            match = re.match(
                r"insert\s+into\s+(\w+)\s*\(([^)]+)\)\s*values\s*\(([^)]+)\)",
                write_sql.lower(),
            )
            if match:
                # Get the table name, columns, and values
                table_name, columns, values = match.groups()
                columns = columns.split(",")
                values = values.split(",")
                # Build the WHERE clause
                where_clause = " AND ".join(
                    [
                        f"{col.strip()}={val.strip()}"
                        for col, val in zip(columns, values)
                    ]
                )
                return f"SELECT * FROM {table_name} WHERE {where_clause}"
            else:
                raise ValueError(f"Unsupported SQL command: {write_sql}")

        elif cmd_type == "delete":
            table_name = parts[2]  # delete from <table_name> ...
            # Return a SELECT statement that selects all data from the table
            return f"SELECT * FROM {table_name} "

        elif cmd_type == "update":
            table_name = parts[1]
            set_idx = parts.index("set")
            where_idx = parts.index("where")
            # Get the field name in the `set` clause
            set_clause = parts[set_idx + 1 : where_idx][0].split("=")[0].strip()
            # Get the condition statement after the `where`
            where_clause = " ".join(parts[where_idx + 1 :])
            # Return a SELECT statement that selects the updated data
            return f"SELECT {set_clause} FROM {table_name} WHERE {where_clause}"
        else:
            raise ValueError(f"Unsupported SQL command type: {cmd_type}")

    def __sql_parse(self, sql):
        sql = sql.strip()
        parsed = sqlparse.parse(sql)[0]
        sql_type = parsed.get_type()
        if sql_type == "CREATE":
            table_name = self._extract_table_name_from_ddl(parsed)
        else:
            table_name = parsed.get_name()

        first_token = parsed.token_first(skip_ws=True, skip_cm=False)
        ttype = first_token.ttype
        logger.info(
            f"SQL:{sql}, ttype:{ttype}, sql_type:{sql_type}, table:{table_name}"
        )
        return parsed, ttype, sql_type, table_name

    def _extract_table_name_from_ddl(self, parsed):
        """Extract table name from CREATE TABLE statement.""" ""
        for token in parsed.tokens:
            if token.ttype is None and isinstance(token, sqlparse.sql.Identifier):
                return token.get_real_name()
        return None

    def get_indexes(self, table_name: str) -> List[Dict]:
        """Get table indexes about specified table.

        Args:
            table_name:(str) table name

        Returns:
            List[Dict]:eg:[{'name': 'idx_key', 'column_names': ['id']}]
        """
        return self._inspector.get_indexes(table_name)

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW CREATE TABLE  {table_name}"))
        ans = cursor.fetchall()
        return ans[0][1]

    def get_fields(self, table_name) -> List[Tuple]:
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                "SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, "
                "COLUMN_COMMENT  from information_schema.COLUMNS where "
                f"table_name='{table_name}'".format(table_name)
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_simple_fields(self, table_name):
        """Get column fields about specified table."""
        return self._query(f"SHOW COLUMNS FROM {table_name}")

    def get_charset(self) -> str:
        """Get character_set."""
        session = self._db_sessions()
        cursor = session.execute(text("SELECT @@character_set_database"))
        character_set = cursor.fetchone()[0]  # type: ignore
        return character_set

    def get_collation(self):
        """Get collation."""
        session = self._db_sessions()
        cursor = session.execute(text("SELECT @@collation_database"))
        collation = cursor.fetchone()[0]
        return collation

    def get_grants(self):
        """Get grant info."""
        session = self._db_sessions()
        cursor = session.execute(text("SHOW GRANTS"))
        grants = cursor.fetchall()
        return grants

    def get_users(self):
        """Get user info."""
        try:
            cursor = self.session.execute(text("SELECT user, host FROM mysql.user"))
            users = cursor.fetchall()
            return [(user[0], user[1]) for user in users]
        except Exception:
            return []

    def get_table_comments(self, db_name: str):
        """Return table comments."""
        cursor = self.session.execute(
            text(
                f"""SELECT table_name, table_comment    FROM information_schema.tables
                    WHERE table_schema = '{db_name}'""".format(
                    db_name
                )
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]

    def get_table_comment(self, table_name: str) -> Dict:
        """Get table comments.

        Args:
            table_name (str): table name
        Returns:
            comment: Dict, which contains text: Optional[str], eg:["text": "comment"]
        """
        return self._inspector.get_table_comment(table_name)

    def get_column_comments(self, db_name: str, table_name: str):
        """Return column comments."""
        cursor = self.session.execute(
            text(
                f"""SELECT column_name, column_comment FROM information_schema.columns
                    WHERE table_schema = '{db_name}' and table_name = '{table_name}'
                """.format(
                    db_name, table_name
                )
            )
        )
        column_comments = cursor.fetchall()
        return [
            (column_comment[0], column_comment[1]) for column_comment in column_comments
        ]

    def get_database_names(self) -> List[str]:
        """Return a list of database names available in the database.

        Returns:
            List[str]: database list
        """
        session = self._db_sessions()
        cursor = session.execute(text(" show databases;"))
        results = cursor.fetchall()
        return [
            d[0]
            for d in results
            if d[0] not in ["information_schema", "performance_schema", "sys", "mysql"]
        ]
