from pandas import DataFrame

from pilot.commands.command_mange import command
from pilot.configs.config import Config
import pandas as pd
import base64
import io
import matplotlib
import seaborn as sns
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

CFG = Config()
logger = build_logger("show_chart_gen", LOGDIR + "show_chart_gen.log")


@command("response_line_chart", "Line chart display, used to display comparative trend analysis data", '"speak": "<speak>", "df":"<data frame>"')
def response_line_chart(speak: str,  df: DataFrame) -> str:
    logger.info(f"response_line_chart:{speak},")

    columns = df.columns.tolist()

    if df.size <= 0:
        raise ValueError("No Data！")
    plt.rcParams["font.family"] = ["sans-serif"]
    rc = {"font.sans-serif": "SimHei", "axes.unicode_minus": False}
    sns.set_style(rc={'font.sans-serif': "Microsoft Yahei"})
    sns.set(context="notebook", style="ticks", color_codes=True, rc=rc)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    sns.lineplot(df, x=columns[0], y=columns[1], ax=ax)
    plt.title("")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    data = base64.b64encode(buf.getvalue()).decode("ascii")

    html_img = f"""<h5>{speak}</h5><img style='max-width: 100%; max-height: 70%;'  src="data:image/png;base64,{data}" />"""
    return html_img



@command("response_bar_chart", "Histogram, suitable for comparative analysis of multiple target values",  '"speak": "<speak>", "df":"<data frame>"')
def response_bar_chart(speak: str,  df: DataFrame) -> str:
    logger.info(f"response_bar_chart:{speak},")
    columns = df.columns.tolist()
    if df.size <= 0:
        raise ValueError("No Data！")
    plt.rcParams["font.family"] = ["sans-serif"]
    rc = {'font.sans-serif': "Microsoft Yahei"}
    sns.set(context="notebook",  color_codes=True, rc=rc)
    sns.set_style("dark")
    sns.color_palette("hls", 10)
    sns.hls_palette(8, l=.5, s=.7)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    plt.ticklabel_format(style='plain')
    sns.barplot(df, x=df[columns[0]], y=df[columns[1]], ax=ax)

    plt.title("")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    data = base64.b64encode(buf.getvalue()).decode("ascii")

    html_img = f"""<h5>{speak}</h5><img style='max-width: 100%; max-height: 70%;'  src="data:image/png;base64,{data}" />"""
    return html_img



@command("response_pie_chart", "Pie chart, suitable for scenarios such as proportion and distribution statistics",  '"speak": "<speak>", "df":"<data frame>"')
def response_pie_chart(speak: str,  df: DataFrame) -> str:
    logger.info(f"response_pie_chart:{speak},")
    columns = df.columns.tolist()
    if df.size <= 0:
        raise ValueError("No Data！")
    plt.rcParams["font.family"] = ["sans-serif"]
    rc = {"font.sans-serif": "SimHei", "axes.unicode_minus": False}
    sns.set_style(rc={'font.sans-serif': "Microsoft Yahei"})
    sns.set(context="notebook", style="ticks", color_codes=True, rc=rc)
    sns.set_palette("Set3")  # 设置颜色主题

    # fig, ax = plt.pie(df[columns[1]], labels=df[columns[0]], autopct='%1.1f%%', startangle=90)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    ax = df.plot(kind='pie', y=columns[1], ax=ax,  labels=df[columns[0]].values,  startangle=90, autopct='%1.1f%%')
    # 手动设置 labels 的位置和大小
    ax.legend(loc='upper right', bbox_to_anchor=(1, 1, 1, 1), labels=df[columns[0]].values, fontsize=10)

    plt.axis('equal')  # 使饼图为正圆形
    # plt.title(columns[0])

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    data = base64.b64encode(buf.getvalue()).decode("ascii")

    html_img = f"""<h5>{speak}</h5><img style='max-width: 100%; max-height: 70%;'  src="data:image/png;base64,{data}" />"""
    return html_img