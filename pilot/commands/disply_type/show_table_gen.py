import pandas as pd
from pandas import DataFrame

from pilot.commands.command_mange import command
from pilot.configs.config import Config

from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

CFG = Config()
logger = build_logger("show_table_gen", LOGDIR + "show_table_gen.log")


@command(
    "response_table",
    "Table display, suitable for display with many display columns or non-numeric columns",
    '"speak": "<speak>", "df":"<data frame>"',
)
def response_table(speak: str, df: DataFrame) -> str:
    logger.info(f"response_table:{speak}")
    html_table = df.to_html(index=False, escape=False, sparsify=False)
    table_str = "".join(html_table.split())
    html = f"""<div class="w-full overflow-auto">{table_str}</div>"""
    view_text = f"##### {str(speak)}" + "\n" + html.replace("\n", " ")
    return view_text
