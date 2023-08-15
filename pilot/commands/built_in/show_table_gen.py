import pandas as pd

from pilot.commands.command_mange import command
from pilot.configs.config import Config

from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

CFG = Config()
logger = build_logger("show_table_gen", LOGDIR + "show_table_gen.log")


@command("response_table", "Use table to display SQL data", '"speak": "<speak>", "sql":"<sql>","db_name":"<db_name>"')
def response_table(speak: str, sql: str, db_name: str) -> str:
    logger.info(f"response_table:{speak},{sql},{db_name}")
    df = pd.read_sql(sql, CFG.LOCAL_DB_MANAGE.get_connect(db_name))
    html_table = df.to_html(index=False, escape=False, sparsify=False)
    table_str = "".join(html_table.split())
    html = f"""<div class="w-full overflow-auto">{table_str}</div>"""
    view_text = f"##### {str(speak)}" + "\n" + html.replace("\n", " ")
    return view_text
