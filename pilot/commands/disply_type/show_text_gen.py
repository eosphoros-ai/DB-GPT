import pandas as pd
from pandas import DataFrame

from pilot.commands.command_mange import command
from pilot.configs.config import Config
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

CFG = Config()
logger = build_logger("show_table_gen", LOGDIR + "show_table_gen.log")


@command(
    "response_data_text",
    "Text display, the default display method, suitable for single-line or simple content display",
    '"speak": "<speak>", "df":"<data frame>"',
)
def response_data_text(speak: str, df: DataFrame) -> str:
    logger.info(f"response_data_text:{speak}")
    data = df.values

    row_size = data.shape[0]
    value_str = ""
    text_info = ""
    if row_size > 1:
        html_table = df.to_html(index=False, escape=False, sparsify=False)
        table_str = "".join(html_table.split())
        html = f"""<div class="w-full overflow-auto">{table_str}</div>"""
        text_info = f"##### {str(speak)}" + "\n" + html.replace("\n", " ")
    elif row_size == 1:
        row = data[0]
        for value in row:
            if value_str:
                value_str = value_str + f", ** {value} **"
            else:
                value_str = f" ** {value} **"
            text_info = f"{speak}: {value_str}"
    else:
        text_info = f"##### {speak}: _没有找到可用的数据_"
    return text_info
