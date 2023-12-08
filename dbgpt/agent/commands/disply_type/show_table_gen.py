from pandas import DataFrame

from dbgpt.agent.commands.command_mange import command

import logging

logger = logging.getLogger(__name__)


@command(
    "response_table",
    "Table display, suitable for display with many display columns or non-numeric columns",
    '"df":"<data frame>"',
)
def response_table(df: DataFrame) -> str:
    logger.info(f"response_table")
    html_table = df.to_html(index=False, escape=False, sparsify=False)
    table_str = "".join(html_table.split())
    table_str = table_str.replace("\n", " ")
    html = f""" \n<div class="w-full overflow-auto">{table_str}</div>\n """
    return html
