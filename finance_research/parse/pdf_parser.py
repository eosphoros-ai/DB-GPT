"""PDF financial report parsing (text + tables with page info)."""

from typing import BinaryIO, List, Tuple, Union

import pandas as pd


def extract_pdf_text(path: Union[str, BinaryIO]) -> List[Tuple[int, str]]:
    """Return a list of ``(page_number, text)`` tuples from a PDF."""
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            pages.append((idx, page.extract_text() or ""))
    return pages


def extract_pdf_tables(
    path: Union[str, BinaryIO],
) -> List[Tuple[int, int, pd.DataFrame]]:
    """Return a list of ``(page, table_index, DataFrame)`` tuples.

    Uses pdfplumber coordinates so cross-page tables can be reconstructed
    by comparing repeated header rows.
    """
    import pdfplumber

    tables = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for idx, table in enumerate(page.extract_tables()):
                if not table:
                    continue
                df = pd.DataFrame(table[1:], columns=table[0])
                tables.append((page_no, idx, df))
    return tables
