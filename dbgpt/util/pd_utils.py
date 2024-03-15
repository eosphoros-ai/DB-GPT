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
