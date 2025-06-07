import math

# def csv_colunm_foramt(val):
#     if str(val).find("$") >= 0:
#         return float(val.replace("$", "").replace(",", ""))
#     if str(val).find("¥") >= 0:
#         return float(val.replace("¥", "").replace(",", ""))
#     return val
import pandas as pd


def csv_colunm_foramt(val):
    try:
        if pd.isna(val):
            return math.nan
        if str(val).find("$") >= 0:
            return float(val.replace("$", "").replace(",", ""))
        if str(val).find("¥") >= 0:
            return float(val.replace("¥", "").replace(",", ""))
        return val
    except ValueError:
        return val


def df_to_markdown(df: pd.DataFrame, index=False) -> str:
    """Convert a pandas DataFrame to a Markdown table."""
    columns = df.columns
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"

    rows = []
    for _, row in df.iterrows():
        row_str = "| " + " | ".join(map(str, row.values)) + " |"
        rows.append(row_str)

    if index:
        header = "| index | " + " | ".join(columns) + " |"
        separator = "| --- | " + " | ".join(["---"] * len(columns)) + " |"
        rows = []
        for idx, row in df.iterrows():
            row_str = f"| {idx} | " + " | ".join(map(str, row.values)) + " |"
            rows.append(row_str)

    return "\n".join([header, separator] + rows)
