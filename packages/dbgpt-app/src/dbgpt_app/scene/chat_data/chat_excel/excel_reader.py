import io
import logging
import os
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional

import chardet
import duckdb
import numpy as np
import pandas as pd
import sqlparse

from dbgpt.util.file_client import FileClient
from dbgpt.util.pd_utils import csv_colunm_foramt

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


class TransformedExcelResponse(NamedTuple):
    description: str
    columns: List[Dict[str, str]]
    plans: List[str]


def excel_colunm_format(old_name: str) -> str:
    new_column = old_name.strip()
    new_column = new_column.replace(" ", "_")
    return new_column


def add_quotes_to_chinese_columns(sql, column_names=[]):
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        process_statement(stmt, column_names)
    return str(parsed[0])


def process_statement(statement, column_names=[]):
    if isinstance(statement, sqlparse.sql.IdentifierList):
        for identifier in statement.get_identifiers():
            process_identifier(identifier)
    elif isinstance(statement, sqlparse.sql.Identifier):
        process_identifier(statement, column_names)
    elif isinstance(statement, sqlparse.sql.TokenList):
        for item in statement.tokens:
            process_statement(item)


def process_identifier(identifier, column_names=[]):
    # if identifier.has_alias():
    #     alias = identifier.get_alias()
    #     identifier.tokens[-1].value = '[' + alias + ']'
    if hasattr(identifier, "tokens") and identifier.value in column_names:
        if is_chinese(identifier.value):
            new_value = get_new_value(identifier.value)
            identifier.value = new_value
            identifier.normalized = new_value
            identifier.tokens = [sqlparse.sql.Token(sqlparse.tokens.Name, new_value)]
    else:
        if hasattr(identifier, "tokens"):
            for token in identifier.tokens:
                if isinstance(token, sqlparse.sql.Function):
                    process_function(token)
                elif token.ttype in sqlparse.tokens.Name:
                    new_value = get_new_value(token.value)
                    token.value = new_value
                    token.normalized = new_value
                elif token.value in column_names:
                    new_value = get_new_value(token.value)
                    token.value = new_value
                    token.normalized = new_value
                    token.tokens = [sqlparse.sql.Token(sqlparse.tokens.Name, new_value)]


def get_new_value(value):
    return f""" "{value.replace("`", "").replace("'", "").replace('"', "")}" """


def process_function(function):
    function_params = list(function.get_parameters())
    # for param in function_params:
    for i in range(len(function_params)):
        param = function_params[i]
        # 如果参数部分是一个标识符（字段名）
        if isinstance(param, sqlparse.sql.Identifier):
            # 判断是否需要替换字段值
            # if is_chinese(param.value):
            # 替换字段值
            new_value = get_new_value(param.value)
            # new_parameter = sqlparse.sql.Identifier(f'[{param.value}]')
            function_params[i].tokens = [
                sqlparse.sql.Token(sqlparse.tokens.Name, new_value)
            ]
    print(str(function))


def is_chinese(text):
    for char in text:
        if "\u4e00" <= char <= "\u9fa5":  # BMP中的常用汉字范围
            return True
    return False


def read_from_df(
    db: "DuckDBPyConnection",
    file_path,
    file_name: str,
    table_name: str,
):
    file_client = FileClient()
    file_info = file_client.read_file(conv_uid=None, file_key=file_path)

    result = chardet.detect(file_info)
    encoding = result["encoding"]
    confidence = result["confidence"]

    logger.info(
        f"File Info:{len(file_info)},Detected Encoding: {encoding} "
        f"(Confidence: {confidence})"
    )
    # read excel file
    if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df_tmp = pd.read_excel(file_info, index_col=False)
        df = pd.read_excel(
            file_info,
            index_col=False,
            converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])},
        )
    elif file_name.endswith(".csv"):
        df_tmp = pd.read_csv(
            file_info if isinstance(file_info, str) else io.BytesIO(file_info),
            index_col=False,
            encoding=encoding,
        )
        df = pd.read_csv(
            file_info if isinstance(file_info, str) else io.BytesIO(file_info),
            index_col=False,
            encoding=encoding,
            converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])},
        )
    else:
        raise ValueError("Unsupported file format.")

    df.replace("", np.nan, inplace=True)

    unnamed_columns_tmp = [
        col
        for col in df_tmp.columns
        if col.startswith("Unnamed") and df_tmp[col].isnull().all()
    ]
    df_tmp.drop(columns=unnamed_columns_tmp, inplace=True)

    df = df[df_tmp.columns.values]

    columns_map = {}
    for column_name in df_tmp.columns:
        df[column_name] = df[column_name].astype(str)
        columns_map.update({column_name: excel_colunm_format(column_name)})
        try:
            df[column_name] = pd.to_datetime(df[column_name]).dt.strftime("%Y-%m-%d")
        except ValueError:
            try:
                df[column_name] = pd.to_numeric(df[column_name])
            except ValueError:
                try:
                    df[column_name] = df[column_name].astype(str)
                except Exception:
                    print("Can't transform column: " + column_name)

    df = df.rename(columns=lambda x: x.strip().replace(" ", "_"))
    # write data in duckdb
    db.register("temp_df_table", df)
    # The table is explicitly created due to the issue at
    # https://github.com/eosphoros-ai/DB-GPT/issues/2437.
    db.execute(f"CREATE TABLE {table_name} AS SELECT * FROM temp_df_table")
    return table_name


def read_direct(
    db: "DuckDBPyConnection",
    file_path: str,
    file_name: str,
    table_name: str,
):
    try:
        # Try to import data automatically, It will automatically detect from the file
        # extension
        db.sql(f"create table {table_name} as SELECT * FROM '{file_path}'")
        return
    except Exception as e:
        logger.warning(f"Error while reading file: {str(e)}")
    file_extension = os.path.splitext(file_path)[1]
    load_params = {}
    if file_extension == ".csv":
        load_func = "read_csv"
        load_params = {}
    elif file_extension == ".xlsx":
        load_func = "read_xlsx"
        load_params["empty_as_varchar"] = "true"
        load_params["ignore_errors"] = "true"
    elif file_extension == ".xls":
        return read_from_df(db, file_path, file_name, table_name)
    elif file_extension == ".json":
        load_func = "read_json_auto"
    elif file_extension == ".parquet":
        load_func = "read_parquet"
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

    func_args = ", ".join([f"{k}={v}" for k, v in load_params.items()])
    if func_args:
        from_exp = f"FROM {load_func}('{file_path}', {func_args})"
    else:
        from_exp = f"FROM {load_func}('{file_path}')"
    load_sql = f"create table {table_name} as SELECT * {from_exp}"
    try:
        db.sql(load_sql)
    except Exception as e:
        logger.warning(f"Error while reading file: {str(e)}")
        return read_from_df(db, file_path, file_name, table_name)


class ExcelReader:
    def __init__(
        self,
        conv_uid: str,
        file_path: str,
        file_name: Optional[str] = None,
        read_type: str = "df",
        database_name: str = ":memory:",
        table_name: str = "data_analysis_table",
        duckdb_extensions_dir: Optional[List[str]] = None,
        force_install: bool = False,
        show_columns: bool = False,
    ):
        if not file_name:
            file_name = os.path.basename(file_path)
        self.conv_uid = conv_uid
        # connect DuckDB

        db_exists = os.path.exists(database_name)

        self.db = duckdb.connect(database=database_name, read_only=False)

        self.temp_table_name = "temp_table"
        self.table_name = table_name

        self.excel_file_name = file_name

        if duckdb_extensions_dir:
            self.install_extension(duckdb_extensions_dir, force_install)

        if not db_exists:
            curr_table = self.temp_table_name
            if read_type == "df":
                read_from_df(self.db, file_path, file_name, curr_table)
            else:
                read_direct(self.db, file_path, file_name, curr_table)
        else:
            curr_table = self.table_name

        if show_columns:
            # Print table schema
            result = self.db.sql(f"DESCRIBE {curr_table}")
            columns = result.fetchall()
            for column in columns:
                print(column)

    def close(self):
        if self.db:
            self.db.close()
            self.db = None

    def __del__(self):
        self.close()

    def run(self, sql, table_name: str, df_res: bool = False, transform: bool = True):
        try:
            if f'"{table_name}"' in sql:
                sql = sql.replace(f'"{table_name}"', table_name)
            if transform:
                sql = add_quotes_to_chinese_columns(sql)
            logger.info(f"To be executed SQL: {sql}")
            if df_res:
                return self.db.sql(sql).df()
            return self._run_sql(sql)
        except Exception as e:
            logger.error(f"excel sql run error!, {str(e)}")
            raise ValueError(f"Data Query Exception!\\nSQL[{sql}].\\nError:{str(e)}")

    def _run_sql(self, sql: str):
        results = self.db.sql(sql)
        columns = []
        for desc in results.description:
            columns.append(desc[0])
        return columns, results.fetchall()

    def get_df_by_sql_ex(self, sql: str, table_name: Optional[str] = None):
        table_name = table_name or self.table_name
        return self.run(sql, table_name, df_res=True)

    def get_sample_data(self, table_name: str):
        columns, datas = self.run(
            f"SELECT * FROM {table_name} USING SAMPLE 5;",
            table_name=table_name,
            transform=False,
        )
        return columns, datas

    def get_columns(self, table_name: str):
        sql = f"""
        SELECT 
    dc.column_name,
    dc.data_type AS column_type,
    CASE WHEN dc.is_nullable THEN 'YES' ELSE 'NO' END AS "null",
    '' AS key,
    '' AS default,
    '' AS "extra",
    dc.comment
FROM duckdb_columns() dc
WHERE dc.table_name = '{table_name}'
AND dc.schema_name = 'main';
"""
        columns, datas = self.run(sql, table_name, transform=False)
        return columns, datas

    def get_create_table_sql(self, table_name: str) -> str:
        sql = f"""SELECT comment, table_name, database_name FROM duckdb_tables() \
        where table_name = '{table_name}'"""

        columns, datas = self.run(sql, table_name, transform=False)
        table_comment = datas[0][0]
        cl_columns, cl_datas = self.get_columns(table_name)
        ddl_sql = f"CREATE TABLE {table_name} (\n"
        column_strs = []
        for cl_data in cl_datas:
            column_name = cl_data[0]
            column_type = cl_data[1]
            nullable = cl_data[2]
            column_key = cl_data[3]
            column_default = cl_data[4]
            column_comment = cl_data[6]
            curr_sql = f"    {column_name} {column_type}"
            if column_key and column_key == "PRI":
                curr_sql += " PRIMARY KEY"
            elif nullable and str(nullable).lower() == "no":
                curr_sql += " NOT NULL"
            elif column_default:
                curr_sql += f" DEFAULT {column_default}"
            elif column_comment:
                curr_sql += f" COMMENT '{column_comment}'"
            column_strs.append(curr_sql)
        ddl_sql += ",\n".join(column_strs)
        if table_comment:
            ddl_sql += f"\n) COMMENT '{table_comment}';"
        else:
            ddl_sql += "\n);"

        return ddl_sql

    def get_summary(self, table_name: str) -> str:
        data = self.run(
            f"SUMMARIZE {table_name}", table_name, transform=False, df_res=True
        ).to_json(force_ascii=False)
        return data

    def transform_table(
        self,
        old_table_name: str,
        new_table_name: str,
        transform: TransformedExcelResponse,
    ):
        table_comment = transform.description
        select_sql_list = []
        new_table = new_table_name

        _, cl_datas = self.get_columns(old_table_name)
        old_col_name_to_type = {cl_data[0]: cl_data[1] for cl_data in cl_datas}

        create_columns = []
        for col_transform in transform.columns:
            old_column_name = col_transform["old_column_name"]
            new_column_name = col_transform["new_column_name"]
            new_column_type = old_col_name_to_type[old_column_name]
            old_column_name = f'"{old_column_name}"'  # 使用双引号括起列名
            select_sql_list.append(f"{old_column_name} AS {new_column_name}")
            create_columns.append(f"{new_column_name} {new_column_type}")

        select_sql = ", ".join(select_sql_list)
        create_columns_str = ", ".join(create_columns)
        create_table_str = f"CREATE TABLE {new_table}(\n{create_columns_str}\n);"
        sql = f"""
    {create_table_str}
    INSERT INTO {new_table} SELECT {select_sql}
    from {old_table_name};
    """
        logger.info("Begin to transform table, SQL: \n" + sql)
        self.db.sql(sql)

        # Transform single quotes in table comments, then execute separately
        escaped_table_comment = table_comment.replace("'", "''")
        table_comment_sql = ""
        try:
            table_comment_sql = (
                f"COMMENT ON TABLE {new_table} IS '{escaped_table_comment}';"
            )
            self.db.sql(table_comment_sql)
            logger.info(f"Added comment to table {new_table}")
        except Exception as e:
            logger.warning(
                f"Error while adding table comment: {str(e)}\nSQL: {table_comment_sql}"
            )

        for col_transform in transform.columns:
            column_comment_sql = ""
            new_column_name = ""
            try:
                new_column_name = col_transform["new_column_name"]
                column_description = col_transform["column_description"]
                # In SQL, single quotes within single quotes need to be escaped with
                # two single quotes
                escaped_description = column_description.replace("'", "''")
                column_comment_sql = (
                    f"COMMENT ON COLUMN {new_table}.{new_column_name}"
                    f" IS '{escaped_description}';"
                )
                self.db.sql(column_comment_sql)
                logger.debug(f"Added comment to column {new_table}.{new_column_name}")
            except Exception as e:
                logger.warning(
                    f"Error while adding comment to column {new_column_name}:"
                    f" {str(e)}\nSQL: {column_comment_sql}"
                )

        return new_table

    def install_extension(
        self, duckdb_extensions_dir: Optional[List[str]], force_install: bool = False
    ) -> int:
        if not duckdb_extensions_dir:
            return 0
        cnt = 0
        for extension_dir in duckdb_extensions_dir:
            if not os.path.exists(extension_dir):
                logger.warning(f"Extension directory not exists: {extension_dir}")
                continue
            extension_files = [
                os.path.join(extension_dir, f)
                for f in os.listdir(extension_dir)
                if f.endswith(".duckdb_extension.gz") or f.endswith(".duckdb_extension")
            ]
            _, extensions = self._query_extension()
            installed_extensions = [ext[0] for ext in extensions if ext[1]]
            for extension_file in extension_files:
                try:
                    extension_name = os.path.basename(extension_file).split(".")[0]
                    if not force_install and extension_name in installed_extensions:
                        logger.info(
                            f"Extension {extension_name} has been installed, skip"
                        )
                        continue
                    self.db.install_extension(
                        extension_file, force_install=force_install
                    )
                    self.db.load_extension(extension_name)
                    cnt += 1
                    logger.info(f"Installed extension {extension_name} for DuckDB")
                except Exception as e:
                    logger.warning(
                        f"Error while installing extension {extension_file}: {str(e)}"
                    )
        logger.debug(f"Installed extensions: {cnt}")
        self.list_extensions()
        return cnt

    def list_extensions(self, stdout=False):
        from prettytable import PrettyTable

        table = PrettyTable()
        columns, datas = self._query_extension()
        table.field_names = columns
        for data in datas:
            table.add_row(data)
        show_str = "DuckDB Extensions:\n"
        show_str += table.get_formatted_string()
        if stdout:
            print(show_str)
        else:
            logger.info(show_str)

    def _query_extension(self):
        return self._run_sql(
            "SELECT extension_name, installed, description FROM duckdb_extensions();"
        )
