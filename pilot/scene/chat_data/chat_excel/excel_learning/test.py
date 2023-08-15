import os
import duckdb
import pandas as pd

import time
from fsspec import filesystem
import  spatial


if __name__ == "__main__":
    # connect = duckdb.connect("/Users/tuyang.yhj/Downloads/example.xlsx")
    #

    def csv_colunm_foramt(val):
        if str(val).find("$") >= 0:
            return float(val.replace('$', '').replace(',', ''))
        if str(val).find("¥") >= 0:
            return float(val.replace('¥', '').replace(',', ''))
        return val

    # 获取当前时间戳，作为代码开始的时间
    start_time = int(time.time() * 1000)

    df = pd.read_excel('/Users/tuyang.yhj/Downloads/example.xlsx')
    # 读取 Excel 文件为 Pandas DataFrame
    df = pd.read_excel('/Users/tuyang.yhj/Downloads/example.xlsx', converters={i: csv_colunm_foramt for i in range(df.shape[1])})

    d = df.values
    print(d.shape[0])
    for row in d:
        print(row[0])
        print(len(row))
    r = df.iterrows()

    # 获取当前时间戳，作为代码结束的时间
    end_time = int(time.time() * 1000)

    print(f"耗时:{(end_time-start_time)/1000}秒")

    # 连接 DuckDB 数据库
    con = duckdb.connect(database=':memory:', read_only=False)

    # 将 DataFrame 写入 DuckDB 数据库中的一个表
    con.register('example', df)

    # 查询 DuckDB 数据库中的表
    conn  = con.cursor()
    results = con.execute('SELECT * FROM example limit 5 ')
    colunms = []
    for descrip in results.description:
        colunms.append(descrip[0])
    print(colunms)
    for row in results.fetchall():
        print(row)


    # 连接 DuckDB 数据库
    # con = duckdb.connect(':memory:')

    # # 加载 spatial 扩展
    # con.execute('install spatial;')
    # con.execute('load spatial;')
    #
    # # 查询 duckdb_internal 系统表，获取扩展列表
    # result = con.execute("SELECT * FROM duckdb_internal.functions WHERE schema='list_extensions';")
    #
    # # 遍历查询结果，输出扩展名称和版本号
    # for row in result:
    #     print(row['name'], row['return_type'])
    # duckdb.read_csv('/Users/tuyang.yhj/Downloads/example_csc.csv')
    # result = duckdb.sql('SELECT * FROM "/Users/tuyang.yhj/Downloads/yhj-zx.csv" ')
    # result = duckdb.sql('SELECT * FROM "/Users/tuyang.yhj/Downloads/example_csc.csv" limit 20')
    # for row in result.fetchall():
    #     print(row)


    # result = con.execute("SELECT * FROM st_read('/Users/tuyang.yhj/Downloads/example.xlsx', layer='Sheet1')")
    # # 遍历查询结果
    # for row in result.fetchall():
    #     print(row)
    print("xx")



