import pandas as pd

from pilot.commands.command_mange import command
from pilot.configs.config import Config
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

CFG = Config()
logger = build_logger("show_table_gen", LOGDIR + "show_table_gen.log")


@command("response_data_text", "Use text to display SQL data",
         '"speak": "<speak>", "sql":"<sql>","db_name":"<db_name>"')
def response_data_text(speak: str, sql: str, db_name: str) -> str:
    logger.info(f"response_data_text:{speak},{sql},{db_name}")
    df = pd.read_sql(sql, CFG.LOCAL_DB_MANAGE.get_connect(db_name))
    data = df.values

    row_size = data.shape[0]
    value_str, text_info = ""
    if row_size > 1:
        html_table = df.to_html(index=False, escape=False, sparsify=False)
        table_str = "".join(html_table.split())
        html = f"""<div class="w-full overflow-auto">{table_str}</div>"""
        text_info = f"##### {str(speak)}" + "\n" + html.replace("\n", " ")
    elif row_size == 1:
        row = data[0]
        for value in row:
            value_str = value_str + f", ** {value} **"
            text_info = f"{speak}: {value_str}"
    else:
        text_info = f"##### {speak}: _没有找到可用的数据_"
    return text_info
