from pandas import DataFrame

from pilot.commands.command_mange import command
from pilot.configs.config import Config
import pandas as pd
import uuid
import io
import os
import matplotlib
import seaborn as sns

# matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontManager

from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

CFG = Config()
logger = build_logger("show_chart_gen", LOGDIR + "show_chart_gen.log")
static_message_img_path = os.path.join(os.getcwd(), "message/img")


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


@command(
    "response_line_chart",
    "Line chart display, used to display comparative trend analysis data",
    '"speak": "<speak>", "df":"<data frame>"',
)
def response_line_chart(speak: str, df: DataFrame) -> str:
    logger.info(f"response_line_chart:{speak},")

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

    rc = {"font.sans-serif": can_use_fonts}
    plt.rcParams["axes.unicode_minus"] = False  # 解决无法显示符号的问题

    sns.set(font=can_use_fonts[0], font_scale=0.8)  # 解决Seaborn中文显示问题
    sns.set_palette("Set3")  # 设置颜色主题
    sns.set_style("dark")
    sns.color_palette("hls", 10)
    sns.hls_palette(8, l=0.5, s=0.7)
    sns.set(context="notebook", style="ticks", rc=rc)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    sns.lineplot(df, x=columns[0], y=columns[1], ax=ax)

    chart_name = "line_" + str(uuid.uuid1()) + ".png"
    chart_path = static_message_img_path + "/" + chart_name
    plt.savefig(chart_path, bbox_inches="tight", dpi=100)

    html_img = f"""<h5>{speak}</h5><img style='max-width: 100%; max-height: 70%;'  src="/images/{chart_name}" />"""
    return html_img


@command(
    "response_bar_chart",
    "Histogram, suitable for comparative analysis of multiple target values",
    '"speak": "<speak>", "df":"<data frame>"',
)
def response_bar_chart(speak: str, df: DataFrame) -> str:
    logger.info(f"response_bar_chart:{speak},")
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

    rc = {"font.sans-serif": can_use_fonts}
    plt.rcParams["axes.unicode_minus"] = False  # 解决无法显示符号的问题
    sns.set(font=can_use_fonts[0], font_scale=0.8)  # 解决Seaborn中文显示问题
    sns.set_palette("Set3")  # 设置颜色主题
    sns.set_style("dark")
    sns.color_palette("hls", 10)
    sns.hls_palette(8, l=0.5, s=0.7)
    sns.set(context="notebook", style="ticks", rc=rc)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    sns.barplot(df, x=df[columns[0]], y=df[columns[1]], ax=ax)

    chart_name = "pie_" + str(uuid.uuid1()) + ".png"
    chart_path = static_message_img_path + "/" + chart_name
    plt.savefig(chart_path, bbox_inches="tight", dpi=100)
    html_img = f"""<h5>{speak}</h5><img style='max-width: 100%; max-height: 70%;'  src="/images/{chart_name}" />"""
    return html_img


@command(
    "response_pie_chart",
    "Pie chart, suitable for scenarios such as proportion and distribution statistics",
    '"speak": "<speak>", "df":"<data frame>"',
)
def response_pie_chart(speak: str, df: DataFrame) -> str:
    logger.info(f"response_pie_chart:{speak},")
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
    # 手动设置 labels 的位置和大小
    ax.legend(
        loc="upper right",
        bbox_to_anchor=(0, 0, 1, 1),
        labels=df[columns[0]].values,
        fontsize=10,
    )

    plt.axis("equal")  # 使饼图为正圆形
    # plt.title(columns[0])

    chart_name = "pie_" + str(uuid.uuid1()) + ".png"
    chart_path = static_message_img_path + "/" + chart_name
    plt.savefig(chart_path, bbox_inches="tight", dpi=100)

    html_img = f"""<h5>{speak.replace("`", '"')}</h5><img style='max-width: 100%; max-height: 70%;'  src="/images/{chart_name}" />"""

    return html_img
