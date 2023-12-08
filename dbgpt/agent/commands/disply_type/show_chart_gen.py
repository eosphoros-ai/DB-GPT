from pandas import DataFrame

from dbgpt.agent.commands.command_mange import command
import pandas as pd
import uuid
import os
import matplotlib
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.font_manager import FontManager
from dbgpt.util.string_utils import is_scientific_notation
from dbgpt.configs.model_config import PILOT_PATH

import logging

logger = logging.getLogger(__name__)


static_message_img_path = os.path.join(PILOT_PATH, "message/img")


def data_pre_classification(df: DataFrame):
    ## Data pre-classification
    columns = df.columns.tolist()

    number_columns = []
    non_numeric_colums = []

    # 收集数据分类小于10个的列
    non_numeric_colums_value_map = {}
    numeric_colums_value_map = {}
    for column_name in columns:
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


def zh_font_set():
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


def format_axis(value, pos):
    # 判断是否为数字
    if is_scientific_notation(value):
        # 判断是否需要进行非科学计数法格式化

        return "{:.2f}".format(value)
    return value


@command(
    "response_line_chart",
    "Line chart display, used to display comparative trend analysis data",
    '"df":"<data frame>"',
)
def response_line_chart(df: DataFrame) -> str:
    logger.info(f"response_line_chart")
    if df.size <= 0:
        raise ValueError("No Data！")
    try:
        # set font
        # zh_font_set()
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

        sns.set(font=can_use_fonts[0], font_scale=0.8)  # 解决Seaborn中文显示问题
        sns.set_palette("Set3")  # 设置颜色主题
        sns.set_style("dark")
        sns.color_palette("hls", 10)
        sns.hls_palette(8, l=0.5, s=0.7)
        sns.set(context="notebook", style="ticks", rc=rc)

        fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
        x, y, non_num_columns, num_colmns = data_pre_classification(df)
        # ## 复杂折线图实现
        if len(num_colmns) > 0:
            num_colmns.append(y)
            df_melted = pd.melt(
                df,
                id_vars=x,
                value_vars=num_colmns,
                var_name="line",
                value_name="Value",
            )
            sns.lineplot(
                data=df_melted, x=x, y="Value", hue="line", ax=ax, palette="Set2"
            )
        else:
            sns.lineplot(data=df, x=x, y=y, ax=ax, palette="Set2")

        ax.yaxis.set_major_formatter(mtick.FuncFormatter(format_axis))
        # ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: "{:,.0f}".format(x)))

        chart_name = "line_" + str(uuid.uuid1()) + ".png"
        chart_path = static_message_img_path + "/" + chart_name
        plt.savefig(chart_path, dpi=100, transparent=True)

        html_img = f"""<img style='max-width: 100%; max-height: 70%;'  src="/images/{chart_name}" />"""
        return html_img
    except Exception as e:
        logging.error("Draw Line Chart Faild!" + str(e), e)
        raise ValueError("Draw Line Chart Faild!" + str(e))


@command(
    "response_bar_chart",
    "Histogram, suitable for comparative analysis of multiple target values",
    '"df":"<data frame>"',
)
def response_bar_chart(df: DataFrame) -> str:
    logger.info(f"response_bar_chart")
    if df.size <= 0:
        raise ValueError("No Data！")

    # set font
    # zh_font_set()
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
    sns.set(font=can_use_fonts[0], font_scale=0.8)  # 解决Seaborn中文显示问题
    sns.set_palette("Set3")  # 设置颜色主题
    sns.set_style("dark")
    sns.color_palette("hls", 10)
    sns.hls_palette(8, l=0.5, s=0.7)
    sns.set(context="notebook", style="ticks", rc=rc)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)

    hue = None
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

    # 设置 y 轴刻度格式为普通数字格式
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(format_axis))
    # ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: "{:,.0f}".format(x)))

    chart_name = "bar_" + str(uuid.uuid1()) + ".png"
    chart_path = static_message_img_path + "/" + chart_name
    plt.savefig(chart_path, dpi=100, transparent=True)
    html_img = f"""<img style='max-width: 100%; max-height: 70%;'  src="/images/{chart_name}" />"""
    return html_img


@command(
    "response_pie_chart",
    "Pie chart, suitable for scenarios such as proportion and distribution statistics",
    '"df":"<data frame>"',
)
def response_pie_chart(df: DataFrame) -> str:
    logger.info(f"response_pie_chart")
    columns = df.columns.tolist()
    if df.size <= 0:
        raise ValueError("No Data！")
    # set font
    # zh_font_set()
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
    plt.rcParams["axes.unicode_minus"] = False  # 解决无法显示符号的问题

    sns.set_palette("Set3")  # 设置颜色主题

    # fig, ax = plt.pie(df[columns[1]], labels=df[columns[0]], autopct='%1.1f%%', startangle=90)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    ax = df.plot(
        kind="pie",
        y=columns[1],
        ax=ax,
        labels=df[columns[0]].values,
        startangle=90,
        autopct="%1.1f%%",
    )

    plt.axis("equal")  # 使饼图为正圆形
    # plt.title(columns[0])

    chart_name = "pie_" + str(uuid.uuid1()) + ".png"
    chart_path = static_message_img_path + "/" + chart_name
    plt.savefig(chart_path, bbox_inches="tight", dpi=100, transparent=True)

    html_img = f"""<img style='max-width: 100%; max-height: 70%;'  src="/images/{chart_name}" />"""

    return html_img
