import duckdb
import os
import pandas as pd

from pilot.common.pd_utils import csv_colunm_foramt

def excel_colunm_format(old_name:str)->str:
    new_column = old_name.strip()
    new_column = new_column.replace(" ", "_")
    return new_column

class ExcelReader:

    def __init__(self, file_path):
        # read excel filt
        df_tmp = pd.read_excel(file_path)


        self.df = pd.read_excel(file_path, converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])})
        self.columns_map = {}
        for column_name in df_tmp.columns:
            self.columns_map.update({column_name: excel_colunm_format(column_name)})

        self.df = self.df.rename(columns=lambda x: x.strip().replace(' ', '_'))

        # connect DuckDB
        self.db = duckdb.connect(database=':memory:', read_only=False)
        file_name = os.path.basename(file_path)
        file_name_without_extension = os.path.splitext(file_name)[0]

        self.excel_file_name = file_name_without_extension
        self.table_name = file_name_without_extension
        # write data in duckdb
        self.db.register(self.table_name, self.df)

    def run(self, sql):
        results = self.db.execute(sql)
        colunms = []
        for descrip in results.description:
            colunms.append(descrip[0])
        return colunms, results.fetchall()

    def get_df_by_sql(self, sql):
        return pd.read_sql(sql, self.db)

    def get_df_by_sql_ex(self, sql):
        colunms, values = self.run(sql)
        return pd.DataFrame(values, columns=colunms)

    def get_sample_data(self):
        return self.run(f'SELECT * FROM {self.table_name} LIMIT 5;')
