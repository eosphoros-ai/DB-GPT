"""Generate text display content for the data frame."""
import logging

from pandas import DataFrame

from ...command_manage import command

logger = logging.getLogger(__name__)


@command(
    "response_data_text",
    "Text display, the default display method, suitable for single-line or "
    "simple content display",
    '"df":"<data frame>"',
)
def response_data_text(df: DataFrame) -> str:
    """Generate text display content for the data frame."""
    logger.info("response_data_text")
    data = df.values

    row_size = data.shape[0]
    value_str = ""
    text_info = ""
    if row_size > 1:
        html_table = df.to_html(index=False, escape=False, sparsify=False)
        table_str = "".join(html_table.split())
        html = f"""<div class="w-full overflow-auto">{table_str}</div>"""
        text_info = html.replace("\n", " ")
    elif row_size == 1:
        row = data[0]
        for value in row:
            if value_str:
                value_str = value_str + f", ** {value} **"
            else:
                value_str = f" ** {value} **"
            text_info = f" {value_str}"
    else:
        text_info = "##### No data found! #####"
    return text_info
