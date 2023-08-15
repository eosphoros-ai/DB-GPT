

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


@command("response_line_chart", "Use line chart to display SQL data", '"speak": "<speak>", "sql":"<sql>","db_name":"<db_name>"')
def response_line_chart(speak: str, sql: str, db_name: str) -> str:
    logger.info(f"response_line_chart:{speak},{sql},{db_name}")
    df = pd.read_sql(sql,  CFG.LOCAL_DB_MANAGE.get_connect(db_name))
    columns = df.columns.tolist()

    if df.size <= 0:
        raise ValueError("No Data！" + sql)
    plt.rcParams["font.family"] = ["sans-serif"]
    rc = {"font.sans-serif": "SimHei", "axes.unicode_minus": False}
    sns.set(context="notebook", style="ticks", color_codes=True, rc=rc)
    plt.subplots(figsize=(8, 5), dpi=100)
    sns.barplot(df, x=columns[0], y=columns[1])
    plt.title("")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    data = base64.b64encode(buf.getvalue()).decode("ascii")

    html_img = f"""<h5>{speak}</h5><img style='max-width: 120%; max-height: 80%;'  src="data:image/png;base64,{data}" />"""
    return html_img



@command("response_bar_chart", "Use bar chart to display SQL data", '"speak": "<speak>", "sql":"<sql>","db_name":"<db_name>"')
def response_bar_chart(speak: str, sql: str, db_name: str) -> str:
    """
    """
    pass


@command("response_pie_chart", "Use pie chart to display SQL data", '"speak": "<speak>", "sql":"<sql>","db_name":"<db_name>"')
def response_pie_chart(speak: str, sql: str, db_name: str) -> str:
    """
    """
    pass