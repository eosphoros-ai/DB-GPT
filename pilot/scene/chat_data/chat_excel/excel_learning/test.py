import os
import duckdb
import pandas as pd
import matplotlib
import seaborn as sns

import matplotlib.pyplot as plt
import time
from fsspec import filesystem
import  spatial

from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader


if __name__ == "__main__":
    # connect = duckdb.connect("/Users/tuyang.yhj/Downloads/example.xlsx")
    #
    excel_reader = ExcelReader("/Users/tuyang.yhj/Downloads/example.xlsx")

    # colunms, datas = excel_reader.run( "SELECT CONCAT(Year, '-', Quarter) AS QuarterYear, SUM(Sales) AS TotalSales FROM example GROUP BY QuarterYear ORDER BY QuarterYear")
    # colunms, datas = excel_reader.run( """ SELECT Country, SUM(Profit) AS Total_Profit FROM example GROUP BY Country; """)
    df = excel_reader.get_df_by_sql_ex("SELECT Country, SUM(Profit) AS Total_Profit FROM example GROUP BY Country;")
    columns = df.columns.tolist()
    plt.rcParams["font.family"] = ["sans-serif"]
    rc = {"font.sans-serif": "SimHei", "axes.unicode_minus": False}
    sns.set_style(rc={'font.sans-serif': "Microsoft Yahei"})
    sns.set(context="notebook", style="ticks", color_codes=True, rc=rc)
    sns.set_palette("Set3")  # 设置颜色主题

    # fig, ax = plt.pie(df[columns[1]], labels=df[columns[0]], autopct='%1.1f%%', startangle=90)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    plt.subplots_adjust(top=0.9)
    ax = df.plot(kind='pie', y=columns[1], ax=ax, labels=df[columns[0]].values, startangle=90, autopct='%1.1f%%')
    # 手动设置 labels 的位置和大小
    ax.legend(loc='center left', bbox_to_anchor=(-1, 0.5, 0,0), labels=None, fontsize=10)
    plt.axis('equal')  # 使饼图为正圆形
    plt.show()
    #
    #
    # def csv_colunm_foramt(val):
    #     if str(val).find("$") >= 0:
    #         return float(val.replace('$', '').replace(',', ''))
    #     if str(val).find("¥") >= 0:
    #         return float(val.replace('¥', '').replace(',', ''))
    #     return val
    #
    # # 获取当前时间戳，作为代码开始的时间
    # start_time = int(time.time() * 1000)
    #
    # df = pd.read_excel('/Users/tuyang.yhj/Downloads/example.xlsx')
    # # 读取 Excel 文件为 Pandas DataFrame
    # df = pd.read_excel('/Users/tuyang.yhj/Downloads/example.xlsx', converters={i: csv_colunm_foramt for i in range(df.shape[1])})
    #
    # # d = df.values
    # # print(d.shape[0])
    # # for row in d:
    # #     print(row[0])
    # #     print(len(row))
    # # r = df.iterrows()
    #
    # # 获取当前时间戳，作为代码结束的时间
    # end_time = int(time.time() * 1000)
    #
    # print(f"耗时:{(end_time-start_time)/1000}秒")
    #
    # # 连接 DuckDB 数据库
    # con = duckdb.connect(database=':memory:', read_only=False)
    #
    # # 将 DataFrame 写入 DuckDB 数据库中的一个表
    # con.register('example', df)
    #
    # # 查询 DuckDB 数据库中的表
    # conn  = con.cursor()
    # results = con.execute('SELECT Country, SUM(Profit) AS Total_Profit FROM example GROUP BY Country ORDER BY Total_Profit DESC LIMIT 1;')
    # colunms = []
    # for descrip in results.description:
    #     colunms.append(descrip[0])
    # print(colunms)
    # for row in results.fetchall():
    #     print(row)
    #
    #
    # # 连接 DuckDB 数据库
    # # con = duckdb.connect(':memory:')
    #
    # # # 加载 spatial 扩展
    # # con.execute('install spatial;')
    # # con.execute('load spatial;')
    # #
    # # # 查询 duckdb_internal 系统表，获取扩展列表
    # # result = con.execute("SELECT * FROM duckdb_internal.functions WHERE schema='list_extensions';")
    # #
    # # # 遍历查询结果，输出扩展名称和版本号
    # # for row in result:
    # #     print(row['name'], row['return_type'])
    # # duckdb.read_csv('/Users/tuyang.yhj/Downloads/example_csc.csv')
    # # result = duckdb.sql('SELECT * FROM "/Users/tuyang.yhj/Downloads/yhj-zx.csv" ')
    # # result = duckdb.sql('SELECT * FROM "/Users/tuyang.yhj/Downloads/example_csc.csv" limit 20')
    # # for row in result.fetchall():
    # #     print(row)
    #
    #
    # # result = con.execute("SELECT * FROM st_read('/Users/tuyang.yhj/Downloads/example.xlsx', layer='Sheet1')")
    # # # 遍历查询结果
    # # for row in result.fetchall():
    # #     print(row)
    # print("xx")
    #
    #
    #
