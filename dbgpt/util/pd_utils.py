def csv_colunm_foramt(val):
    if str(val).find("$") >= 0:
        return float(val.replace("$", "").replace(",", ""))
    if str(val).find("¥") >= 0:
        return float(val.replace("¥", "").replace(",", ""))
    return val
