import duckdb
import pandas as pd

from pilot.common.pd_utils import csv_colunm_foramt


class ExcelReader:

    def __init__(self, file_path):
        # read excel filt
        df_tmp = pd.read_excel(file_path)
        self.df = pd.read_excel(file_path, converters={i: csv_colunm_foramt for i in range(df_tmp.shape[1])})
        # connect DuckDB
        self.db = duckdb.connect(database=':memory:', read_only=False)

        self.table_name = f"excel"
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
