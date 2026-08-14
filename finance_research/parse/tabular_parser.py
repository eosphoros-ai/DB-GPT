"""CSV / Excel financial data parsing.

Parses tabular files (CSV, XLSX, XLS) into DataFrames plus a readable text
summary, so they can feed the same metric-extraction pipeline used for HTML
and PDF sources.
"""

import io
from typing import Dict, List, Tuple

import pandas as pd


def parse_csv_bytes(
    data: bytes, encoding: str = "utf-8"
) -> Tuple[pd.DataFrame, str]:
    """Parse CSV bytes into a single DataFrame.

    Tries the requested encoding first, then a list of common fallbacks
    (utf-8-sig for BOM, gb18030 for Chinese Excel exports).
    """
    for enc in (encoding, "utf-8-sig", "gb18030", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(data), encoding=enc)
            return df, f"CSV 表格（编码 {enc}）"
        except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
            continue
    raise ValueError("无法解析 CSV 文件：编码无法识别")


def parse_excel_bytes(data: bytes) -> Dict[str, Tuple[pd.DataFrame, str]]:
    """Parse Excel bytes into ``{sheet_name: (DataFrame, label)}``.

    The label carries the sheet/table name so provenance can record it.
    """
    import openpyxl  # noqa: F401 - ensure the dependency is present

    sheets: Dict[str, Tuple[pd.DataFrame, str]] = {}
    workbook = pd.ExcelFile(io.BytesIO(data))
    for sheet_name in workbook.sheet_names:
        df = workbook.parse(sheet_name=sheet_name)
        label = f"Excel 工作表「{sheet_name}」"
        sheets[sheet_name] = (df, label)
    return sheets


def parse_tabular_bytes(
    data: bytes, filename: str = ""
) -> Tuple[List[pd.DataFrame], List[str]]:
    """Dispatch CSV / Excel bytes to the right parser.

    Returns ``(tables, labels)`` where ``labels[i]`` names the source table
    for provenance tracking. The filename extension (or content sniffing)
    decides the format.
    """
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls", ".xlsm")):
        parsed = parse_excel_bytes(data)
        return (
            [df for df, _ in parsed.values()],
            [label for _, label in parsed.values()],
        )
    # Fall back to CSV.
    df, label = parse_csv_bytes(data)
    return [df], [label]


def dataframe_to_text(df: pd.DataFrame, max_rows: int = 200) -> str:
    """Render a DataFrame as a compact, extractable text block."""
    if df is None or df.empty:
        return ""
    # Collapse unnamed columns and drop fully-empty rows for a cleaner text.
    cleaned = df.copy()
    cleaned.columns = [
        str(c) if not str(c).startswith("Unnamed:") else "" for c in cleaned.columns
    ]
    cleaned = cleaned.dropna(how="all")
    return cleaned.head(max_rows).to_string(index=False)
