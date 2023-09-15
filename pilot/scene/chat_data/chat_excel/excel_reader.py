import duckdb
import os
import re
import sqlparse
import pandas as pd
import numpy as np

from pilot.common.pd_utils import csv_colunm_foramt


def excel_colunm_format(old_name: str) -> str:
    new_column = old_name.strip()
    new_column = new_column.replace(" ", "_")
    return new_column


def add_quotes_ex(sql: str, column_names):
    sql = sql.replace("`", '"')
    for column_name in column_names:
        if sql.find(column_name) != -1 and sql.find(f'"{column_name}"') == -1:
            sql = sql.replace(column_name, f'"{column_name}"')
    return sql


def add_quotes(sql, column_names=[]):
    sql = sql.replace("`", "")
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        for token in stmt.tokens:
            deep_quotes(token, column_names)
    return str(parsed[0])


def deep_quotes(token, column_names=[]):
    if hasattr(token, "tokens"):
        for token_child in token.tokens:
            deep_quotes(token_child, column_names)
    else:
        if token.value in column_names:
            token.value = f'"{token.value.replace("`", "")}"'
        elif token.ttype == sqlparse.tokens.Name:
            token.value = f'"{token.value.replace("`", "")}"'


if __name__ == "__main__":
    sql = "SELECT `地区`, (`2021年人口` - `2001年人口`) / `2001年人口` * 100 AS `Population_Growth_Rate` FROM Generated_by_ChatExcel_table1 (2)"
    if f'"Generated_by_ChatExcel_table1 (2)"' not in sql:
        sql = sql.replace(
            "Generated_by_ChatExcel_table1 (2)", f'"Generated_by_ChatExcel_table1 (2)"'
        )
    sql = add_quotes_ex(
        sql, ["地区", "地区代码", "2001年人口", "2006年人口", "2011年人口", "2016年人口", "2021年人口"]
    )
    print(f"excute sql:{sql}")


def is_chinese(string):
    # 使用正则表达式匹配中文字符
    pattern = re.compile(r"[一-龥]")
    match = re.search(pattern, string)
    return match is not None


class ExcelReader:
    def __init__(self, file_path):
        file_name = os.path.basename(file_path)
        file_name_without_extension = os.path.splitext(file_name)[0]

        self.excel_file_name = file_name
        self.extension = os.path.splitext(file_name)[1]
        # read excel file
        if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            df_tmp = pd.read_excel(file_path)
            self.df = pd.read_excel(
                file_path,
                converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])},
            )
        elif file_path.endswith(".csv"):
            df_tmp = pd.read_csv(file_path)
            self.df = pd.read_csv(
                file_path,
                converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])},
            )
        else:
            raise ValueError("Unsupported file format.")

        self.df.replace("", np.nan, inplace=True)
        self.columns_map = {}
        for column_name in df_tmp.columns:
            self.columns_map.update({column_name: excel_colunm_format(column_name)})
            try:
                self.df[column_name] = pd.to_numeric(self.df[column_name])
                self.df[column_name] = self.df[column_name].fillna(0)
            except Exception as e:
                print("transfor column error！" + column_name)

        self.df = self.df.rename(columns=lambda x: x.strip().replace(" ", "_"))

        # connect DuckDB
        self.db = duckdb.connect(database=":memory:", read_only=False)

        self.table_name = "excel_data"
        # write data in duckdb
        self.db.register(self.table_name, self.df)

    def run(self, sql):
        if f'"{self.table_name}"' not in sql:
            sql = sql.replace(self.table_name, f'"{self.table_name}"')
        sql = add_quotes_ex(sql, self.columns_map.values())
        print(f"excute sql:{sql}")
        results = self.db.execute(sql)
        colunms = []
        for descrip in results.description:
            colunms.append(descrip[0])
        return colunms, results.fetchall()

    def get_df_by_sql_ex(self, sql):
        colunms, values = self.run(sql)
        return pd.DataFrame(values, columns=colunms)

    def get_sample_data(self):
        return self.run(f"SELECT * FROM {self.table_name} LIMIT 5;")
