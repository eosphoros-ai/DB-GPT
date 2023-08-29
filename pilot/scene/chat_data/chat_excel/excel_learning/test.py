import os
import duckdb
import pandas as pd
import matplotlib
import seaborn as sns
import uuid
from pandas import DataFrame

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib import font_manager
from matplotlib.font_manager import FontManager

matplotlib.use("Agg")
import time
from fsspec import filesystem
import spatial

from pilot.scene.chat_data.chat_excel.excel_reader import ExcelReader


def data_pre_classification(df: DataFrame):
    ## Data pre-classification
    columns = df.columns.tolist()

    number_columns = []
    non_numeric_colums = []

    # 收集数据分类小于10个的列
    non_numeric_colums_value_map = {}
    numeric_colums_value_map = {}
    for column_name in columns:
        if pd.to_numeric(df[column_name], errors="coerce").notna().all():
            number_columns.append(column_name)
            unique_values = df[column_name].unique()
            numeric_colums_value_map.update({column_name: len(unique_values)})
        else:
            non_numeric_colums.append(column_name)
            unique_values = df[column_name].unique()
            non_numeric_colums_value_map.update({column_name: len(unique_values)})

    if len(non_numeric_colums) <= 0:
        sorted_colums_value_map = dict(
            sorted(numeric_colums_value_map.items(), key=lambda x: x[1])
        )
        numeric_colums_sort_list = list(sorted_colums_value_map.keys())
        x_column = number_columns[0]
        hue_column = numeric_colums_sort_list[0]
        y_column = numeric_colums_sort_list[1]
    elif len(number_columns) <= 0:
        raise ValueError("Have No numeric Column！")
    else:
        # 数字和非数字都存在多列，放弃部分数字列
        y_column = number_columns[0]
        x_column = non_numeric_colums[0]
        # if len(non_numeric_colums) > 1:
        #
        # else:

        # non_numeric_colums_sort_list.remove(non_numeric_colums[0])
        # hue_column = non_numeric_colums_sort_list
    return x_column, y_column, hue_column


if __name__ == "__main__":
    # connect = duckdb.connect("/Users/tuyang.yhj/Downloads/example.xlsx")
    #

    # fonts = fm.findSystemFonts()
    # for font in fonts:
    #     if 'Hei' in font:
    #         print(font)

    # fm = FontManager()
    # mat_fonts = set(f.name for f in fm.ttflist)
    # for i in mat_fonts:
    #     print(i)
    # print(len(mat_fonts))
    # 获取系统中的默认中文字体名称
    # default_font = fm.fontManager.defaultFontProperties.get_family()

    #
    excel_reader = ExcelReader("/Users/tuyang.yhj/Downloads/example.xlsx")
    #
    # # colunms, datas = excel_reader.run( "SELECT CONCAT(Year, '-', Quarter) AS QuarterYear, SUM(Sales) AS TotalSales FROM example GROUP BY QuarterYear ORDER BY QuarterYear")
    # # colunms, datas = excel_reader.run( """ SELECT Year, SUM(Sales) AS Total_Sales FROM example GROUP BY Year ORDER BY Year; """)
    df = excel_reader.get_df_by_sql_ex(
        """ SELECT Segment, Country, SUM(Sales) AS Total_Sales, SUM(Profit) AS Total_Profit FROM example GROUP BY Segment, Country """
    )

    x, y, hue = data_pre_classification(df)
    print(x, y, hue)

    columns = df.columns.tolist()
    font_names = [
        "Heiti TC",
        "Songti SC",
        "STHeiti Light",
        "Microsoft YaHei",
        "SimSun",
        "SimHei",
        "KaiTi",
    ]
    fm = FontManager()
    mat_fonts = set(f.name for f in fm.ttflist)
    can_use_fonts = []
    for font_name in font_names:
        if font_name in mat_fonts:
            can_use_fonts.append(font_name)
    if len(can_use_fonts) > 0:
        plt.rcParams["font.sans-serif"] = can_use_fonts

    rc = {"font.sans-serif": can_use_fonts}
    plt.rcParams["axes.unicode_minus"] = False  # 解决无法显示符号的问题
    sns.set(font="Heiti TC", font_scale=0.8)  # 解决Seaborn中文显示问题
    sns.set_palette("Set3")  # 设置颜色主题
    sns.set_style("dark")
    sns.color_palette("hls", 10)
    sns.hls_palette(8, l=0.5, s=0.7)
    sns.set(context="notebook", style="ticks", rc=rc)
    # sns.set_palette("Set3")  # 设置颜色主题
    # sns.set_style("dark")
    # sns.color_palette("hls", 10)
    # sns.hls_palette(8, l=.5, s=.7)
    # sns.set(context='notebook', style='ticks', rc=rc)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    # plt.ticklabel_format(style='plain')
    # ax = df.plot(kind='bar', ax=ax)
    # sns.barplot(df, x=x, y=y, hue= "Country", ax=ax)
    sns.catplot(data=df, x=x, y=y, hue="Country", kind="bar")
    # 设置 y 轴刻度格式为普通数字格式
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: "{:,.0f}".format(x)))

    # fonts = font_manager.findSystemFonts()
    # font_path = ""
    # for font in fonts:
    #     if "Heiti" in font:
    #         font_path = font
    # my_font = font_manager.FontProperties(fname=font_path)
    # plt.title("测试", fontproperties=my_font)
    # plt.ylabel(columns[1], fontproperties=my_font)
    # plt.xlabel(columns[0], fontproperties=my_font)

    chart_name = "bar_" + str(uuid.uuid1()) + ".png"
    chart_path = chart_name
    plt.savefig(chart_path, bbox_inches="tight", dpi=100)

    # sns.set(context="notebook", style="ticks", color_codes=True)
    # sns.set_palette("Set3")  # 设置颜色主题
    #
    # # fig, ax = plt.pie(df[columns[1]], labels=df[columns[0]], autopct='%1.1f%%', startangle=90)
    # fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    # plt.subplots_adjust(top=0.9)
    # ax = df.plot(kind='pie', y=columns[1], ax=ax, labels=df[columns[0]].values, startangle=90, autopct='%1.1f%%')
    # # 手动设置 labels 的位置和大小
    # ax.legend(loc='center left', bbox_to_anchor=(-1, 0.5, 0,0), labels=None, fontsize=10)
    # plt.axis('equal')  # 使饼图为正圆形
    # plt.show()

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
