from __future__ import annotations
import sqlparse
import regex as re
import warnings
from typing import Any, Iterable, List, Optional
from pydantic import BaseModel, Field, root_validator, validator, Extra
from abc import ABC, abstractmethod
import sqlalchemy
from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.schema import CreateTable
from sqlalchemy.orm import sessionmaker, scoped_session


def _format_index(index: sqlalchemy.engine.interfaces.ReflectedIndex) -> str:
    return (
        f'Name: {index["name"]}, Unique: {index["unique"]},'
        f' Columns: {str(index["column_names"])}'
    )


class Database:
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
        custom_table_info: Optional[dict] = None,
        view_support: bool = False,
    ):
        """Create engine from database URI."""
        self._engine = engine
        self._schema = schema
        if include_tables and ignore_tables:
            raise ValueError("Cannot specify both include_tables and ignore_tables")

        self._inspector = inspect(self._engine)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)

        self._db_sessions = Session

        self._all_tables = set()
        self.view_support = False
        self._usable_tables = set()
        self._include_tables = set()
        self._ignore_tables = set()
        self._custom_table_info = set()
        self._indexes_in_table_info = set()
        self._usable_tables = set()
        self._usable_tables = set()
        self._sample_rows_in_table_info = set()
        self._indexes_in_table_info = indexes_in_table_info

    @classmethod
    def from_uri(
        cls, database_uri: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> Database:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine(database_uri, **_engine_args), **kwargs)

    @property
    def dialect(self) -> str:
        """Return string representation of dialect to use."""
        return self._engine.dialect.name

    def get_usable_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        if self._include_tables:
            return self._include_tables
        return self._all_tables - self._ignore_tables

    def get_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        warnings.warn(
            "This method is deprecated - please use `get_usable_table_names`."
        )
        return self.get_usable_table_names()

    def get_session_db(self, connect):
        sql = text(f"select DATABASE()")
        cursor = connect.execute(sql)
        result = cursor.fetchone()[0]
        return result

    def get_session(self, db_name: str):
        session = self._db_sessions()

        self._metadata = MetaData()
        # sql = f"use {db_name}"
        sql = text(f"use `{db_name}`")
        session.execute(sql)

        # 处理表信息数据

        self._metadata.reflect(bind=self._engine, schema=db_name)

        # including view support by adding the views as well as tables to the all
        # tables list if view_support is True
        self._all_tables = set(
            self._inspector.get_table_names(schema=db_name)
            + (
                self._inspector.get_view_names(schema=db_name)
                if self.view_support
                else []
            )
        )

        return session

    def get_current_db_name(self, session) -> str:
        return session.execute(text("SELECT DATABASE()")).scalar()

    def table_simple_info(self, session):
        _sql = f"""
                select concat(table_name, "(" , group_concat(column_name), ")") as schema_info from information_schema.COLUMNS where table_schema="{self.get_current_db_name(session)}" group by TABLE_NAME;
            """
        cursor = session.execute(text(_sql))
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

    def __write(self, session, write_sql):
        print(f"Write[{write_sql}]")
        db_cache = self.get_session_db(session)
        result = session.execute(text(write_sql))
        session.commit()
        # TODO  Subsequent optimization of dynamically specified database submission loss target problem
        session.execute(text(f"use `{db_cache}`"))
        print(f"SQL[{write_sql}], result:{result.rowcount}")
        return result.rowcount

    def __query(self, session, query, fetch: str = "all"):
        """
        only for query
        Args:
            session:
            query:
            fetch:

        Returns:

        """
        print(f"Query[{query}]")
        if not query:
            return []
        cursor = session.execute(text(query))
        if cursor.returns_rows:
            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = cursor.fetchone()[0]  # type: ignore
            else:
                raise ValueError("Fetch parameter must be either 'one' or 'all'")
            field_names = tuple(i[0:] for i in cursor.keys())

            result = list(result)
            result.insert(0, field_names)
            return result

    def run(self, session, command: str, fetch: str = "all") -> List:
        """Execute a SQL command and return a string representing the results."""
        print("SQL:" + command)
        if not command:
            return []
        parsed, ttype, sql_type = self.__sql_parse(command)
        if ttype == sqlparse.tokens.DML:
            if sql_type == "SELECT":
                return self.__query(session, command, fetch)
            else:
                self.__write(session, command)
                select_sql = self.convert_sql_write_to_select(command)
                print(f"write result query:{select_sql}")
                return self.__query(session, select_sql)

        else:
            print(f"DDL execution determines whether to enable through configuration ")
            cursor = session.execute(text(command))
            session.commit()
            if cursor.returns_rows:
                result = cursor.fetchall()
                field_names = tuple(i[0:] for i in cursor.keys())
                result = list(result)
                result.insert(0, field_names)
                print("DDL Result:" + str(result))

                return result
            else:
                return []

    def run_no_throw(self, session, command: str, fetch: str = "all") -> List:
        """Execute a SQL command and return a string representing the results.

        If the statement returns rows, a string of the results is returned.
        If the statement returns no rows, an empty string is returned.

        If the statement throws an error, the error message is returned.
        """
        try:
            return self.run(session, command, fetch)
        except SQLAlchemyError as e:
            """Format the error message"""
            return f"Error: {e}"

    def get_database_list(self):
        session = self._db_sessions()
        cursor = session.execute(text(" show databases;"))
        results = cursor.fetchall()
        return [
            d[0]
            for d in results
            if d[0] not in ["information_schema", "performance_schema", "sys", "mysql"]
        ]

    def convert_sql_write_to_select(self, write_sql):
        """
        SQL classification processing
        author:xiangh8
        Args:
            sql:

        Returns:

        """
        # 将SQL命令转换为小写，并按空格拆分
        parts = write_sql.lower().split()
        # 获取命令类型（insert, delete, update）
        cmd_type = parts[0]

        # 根据命令类型进行处理
        if cmd_type == "insert":
            match = re.match(
                r"insert into (\w+) \((.*?)\) values \((.*?)\)", write_sql.lower()
            )
            if match:
                table_name, columns, values = match.groups()
                # 将字段列表和值列表分割为单独的字段和值
                columns = columns.split(",")
                values = values.split(",")
                # 构造 WHERE 子句
                where_clause = " AND ".join(
                    [
                        f"{col.strip()}={val.strip()}"
                        for col, val in zip(columns, values)
                    ]
                )
                return f"SELECT * FROM {table_name} WHERE {where_clause}"

        elif cmd_type == "delete":
            table_name = parts[2]  # delete from <table_name> ...
            # 返回一个select语句，它选择该表的所有数据
            return f"SELECT * FROM {table_name}"

        elif cmd_type == "update":
            table_name = parts[1]
            set_idx = parts.index("set")
            where_idx = parts.index("where")
            # 截取 `set` 子句中的字段名
            set_clause = parts[set_idx + 1 : where_idx][0].split("=")[0].strip()
            # 截取 `where` 之后的条件语句
            where_clause = " ".join(parts[where_idx + 1 :])
            # 返回一个select语句，它选择更新的数据
            return f"SELECT {set_clause} FROM {table_name} WHERE {where_clause}"
        else:
            raise ValueError(f"Unsupported SQL command type: {cmd_type}")

    def __sql_parse(self, sql):
        sql = sql.strip()
        parsed = sqlparse.parse(sql)[0]
        sql_type = parsed.get_type()

        first_token = parsed.token_first(skip_ws=True, skip_cm=False)
        ttype = first_token.ttype
        print(f"SQL:{sql}, ttype:{ttype}, sql_type:{sql_type}")
        return parsed, ttype, sql_type

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW INDEXES FROM {table_name}"))
        indexes = cursor.fetchall()
        return [(index[2], index[4]) for index in indexes]

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW CREATE TABLE  {table_name}"))
        ans = cursor.fetchall()
        return ans[0][1]

    def get_fields(self, table_name):
        """Get column fields about specified table."""
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE, COLUMN_COMMENT  from information_schema.COLUMNS where table_name='{table_name}'".format(
                    table_name
                )
            )
        )
        fields = cursor.fetchall()
        return [(field[0], field[1], field[2], field[3], field[4]) for field in fields]

    def get_charset(self):
        """Get character_set."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SELECT @@character_set_database"))
        character_set = cursor.fetchone()[0]
        return character_set

    def get_collation(self):
        """Get collation."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SELECT @@collation_database"))
        collation = cursor.fetchone()[0]
        return collation

    def get_grants(self):
        """Get grant info."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW GRANTS"))
        grants = cursor.fetchall()
        return grants

    def get_users(self):
        """Get user info."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SELECT user, host FROM mysql.user"))
        users = cursor.fetchall()
        return [(user[0], user[1]) for user in users]

    def get_table_comments(self, database):
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"""SELECT table_name, table_comment    FROM information_schema.tables   WHERE table_schema = '{database}'""".format(
                    database
                )
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]
