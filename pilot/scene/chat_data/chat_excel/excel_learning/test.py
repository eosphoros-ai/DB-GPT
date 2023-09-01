import os
import duckdb
import pandas as pd
import numpy as np
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
    df_filtered = df.dropna()
    for column_name in columns:
        print(np.issubdtype(df_filtered[column_name].dtype, np.number))
        # if pd.to_numeric(df[column_name], errors='coerce').notna().all():
        # if np.issubdtype(df_filtered[column_name].dtype, np.number):
        if pd.api.types.is_numeric_dtype(df[column_name].dtypes):
            number_columns.append(column_name)
            unique_values = df[column_name].unique()
            numeric_colums_value_map.update({column_name: len(unique_values)})
        else:
            non_numeric_colums.append(column_name)
            unique_values = df[column_name].unique()
            non_numeric_colums_value_map.update({column_name: len(unique_values)})

    sorted_numeric_colums_value_map = dict(
        sorted(numeric_colums_value_map.items(), key=lambda x: x[1])
    )
    numeric_colums_sort_list = list(sorted_numeric_colums_value_map.keys())

    sorted_colums_value_map = dict(
        sorted(non_numeric_colums_value_map.items(), key=lambda x: x[1])
    )
    non_numeric_colums_sort_list = list(sorted_colums_value_map.keys())

    #  Analyze x-coordinate
    if len(non_numeric_colums_sort_list) > 0:
        x_cloumn = non_numeric_colums_sort_list[-1]
        non_numeric_colums_sort_list.remove(x_cloumn)
    else:
        x_cloumn = number_columns[0]
        numeric_colums_sort_list.remove(x_cloumn)

    #  Analyze y-coordinate
    if len(numeric_colums_sort_list) > 0:
        y_column = numeric_colums_sort_list[0]
        numeric_colums_sort_list.remove(y_column)
    else:
        raise ValueError("Not enough numeric columns for chart！")

    return x_cloumn, y_column, non_numeric_colums_sort_list, numeric_colums_sort_list

    #
    # if len(non_numeric_colums) <=0:
    #     sorted_colums_value_map = dict(sorted(numeric_colums_value_map.items(), key=lambda x: x[1]))
    #     numeric_colums_sort_list = list(sorted_colums_value_map.keys())
    #     x_column = number_columns[0]
    #     hue_column = numeric_colums_sort_list[0]
    #     y_column = numeric_colums_sort_list[1]
    #     cols = numeric_colums_sort_list[2:]
    # elif len(number_columns) <=0:
    #     raise ValueError("Have No numeric Column！")
    # else:
    #     # 数字和非数字都存在多列，放弃部分数字列
    #     x_column = non_numeric_colums[0]
    #     y_column = number_columns[0]
    #     if len(non_numeric_colums) > 1:
    #         sorted_colums_value_map = dict(sorted(non_numeric_colums_value_map.items(), key=lambda x: x[1]))
    #         non_numeric_colums_sort_list = list(sorted_colums_value_map.keys())
    #         non_numeric_colums_sort_list.remove(non_numeric_colums[0])
    #         hue_column = non_numeric_colums_sort_list[0]
    #         if len(number_columns) > 1:
    #             # try multiple charts
    #             cols = number_columns.remove( number_columns[0])
    #
    #     else:
    #         sorted_colums_value_map = dict(sorted(numeric_colums_value_map.items(), key=lambda x: x[1]))
    #         numeric_colums_sort_list = list(sorted_colums_value_map.keys())
    #         numeric_colums_sort_list.remove(number_columns[0])
    #         if sorted_colums_value_map[numeric_colums_sort_list[0]].value < 5:
    #             hue_column = numeric_colums_sort_list[0]
    #         if len(number_columns) > 2:
    #             # try multiple charts
    #             cols = numeric_colums_sort_list.remove(numeric_colums_sort_list[0])
    #
    # print(x_column, y_column, hue_column, cols)
    # return x_column, y_column, hue_column


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

    # 创建一个示例 DataFrame
    df = pd.DataFrame(
        {
            "A": [1, 2, 3, None, 5],
            "B": [10, 20, 30, 40, 50],
            "C": [1.1, 2.2, None, 4.4, 5.5],
            "D": ["a", "b", "c", "d", "e"],
        }
    )

    # 判断列是否为数字列
    column_name = "A"  # 要判断的列名
    is_numeric = pd.to_numeric(df[column_name], errors="coerce").notna().all()

    if is_numeric:
        print(
            f"Column '{column_name}' is a numeric column (ignoring null and NaN values in some elements)."
        )
    else:
        print(
            f"Column '{column_name}' is not a numeric column (ignoring null and NaN values in some elements)."
        )

    #
    # excel_reader = ExcelReader("/Users/tuyang.yhj/Downloads/example.xlsx")
    excel_reader = ExcelReader("/Users/tuyang.yhj/Downloads/yhj-zx.csv")
    #
    # # colunms, datas = excel_reader.run( "SELECT CONCAT(Year, '-', Quarter) AS QuarterYear, SUM(Sales) AS TotalSales FROM example GROUP BY QuarterYear ORDER BY QuarterYear")
    # # colunms, datas = excel_reader.run( """ SELECT Year, SUM(Sales) AS Total_Sales FROM example GROUP BY Year ORDER BY Year; """)
    # df = excel_reader.get_df_by_sql_ex(""" SELECT Segment, Country, SUM(Sales) AS Total_Sales, SUM(Profit) AS Total_Profit FROM example GROUP BY Segment, Country """)
    df = excel_reader.get_df_by_sql_ex(
        """ SELECT 大项, AVG(实际) AS 平均实际支出, AVG(已支出) AS 平均已支出 FROM yhj-zx GROUP BY 大项"""
    )

    for column_name in df.columns.tolist():
        print(column_name + ":" + str(df[column_name].dtypes))
        print(
            column_name
            + ":"
            + str(pd.api.types.is_numeric_dtype(df[column_name].dtypes))
        )

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

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    # plt.ticklabel_format(style='plain')
    # ax = df.plot(kind='bar', ax=ax)
    # sns.barplot(df, x=x, y="Total_Sales", hue='Country', ax=ax)
    # sns.barplot(df, x=x, y="Total_Profit", hue='Country', ax=ax)

    # sns.catplot(data=df, x=x, y=y, hue='Country',  kind='bar')
    # x, y, non_num_columns, num_colmns = data_pre_classification(df)
    # print(x, y, str(non_num_columns), str(num_colmns))
    ## 复杂折线图实现
    # if len(num_colmns) > 0:
    #     num_colmns.append(y)
    #     df_melted = pd.melt(
    #         df, id_vars=x, value_vars=num_colmns, var_name="line", value_name="Value"
    #     )
    #     sns.lineplot(data=df_melted, x=x, y="Value", hue="line", ax=ax, palette="Set2")
    # else:
    #     sns.lineplot(data=df, x=x, y=y, ax=ax, palette="Set2")

    hue = None
    ## 复杂柱状图实现
    x, y, non_num_columns, num_colmns = data_pre_classification(df)

    if len(non_num_columns) >= 1:
        hue = non_num_columns[0]

    if len(num_colmns) >= 1:
        if hue:
            if len(num_colmns) >= 2:
                can_use_columns = num_colmns[:2]
            else:
                can_use_columns = num_colmns
            sns.barplot(data=df, x=x, y=y, hue=hue, palette="Set2", ax=ax)
            for sub_y_column in can_use_columns:
                sns.barplot(
                    data=df, x=x, y=sub_y_column, hue=hue, palette="Set2", ax=ax
                )
        else:
            if len(num_colmns) > 5:
                can_use_columns = num_colmns[:5]
            else:
                can_use_columns = num_colmns
            can_use_columns.append(y)

            df_melted = pd.melt(
                df,
                id_vars=x,
                value_vars=can_use_columns,
                var_name="line",
                value_name="Value",
            )
            sns.barplot(
                data=df_melted, x=x, y="Value", hue="line", palette="Set2", ax=ax
            )
    else:
        sns.barplot(data=df, x=x, y=y, hue=hue, palette="Set2", ax=ax)

    # # 转换 DataFrame 格式
    # df_melted = pd.melt(df, id_vars=x, value_vars=['Total_Sales', 'Total_Profit'], var_name='line', value_name='y')
    #
    # # 绘制多列柱状图
    #
    # sns.barplot(data=df, x=x, y="Total_Sales", hue = "Country",  palette="Set2", ax=ax)
    # sns.barplot(data=df, x=x, y="Total_Profit", hue = "Country",  palette="Set1", ax=ax)

    # 设置 y 轴刻度格式为普通数字格式
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: "{:,.0f}".format(x)))

    chart_name = "bar_" + str(uuid.uuid1()) + ".png"
    chart_path = chart_name
    plt.savefig(chart_path, bbox_inches="tight", dpi=100)

    #
