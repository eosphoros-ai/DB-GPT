"""Load real workbook header cell types through the default ChatExcel reader."""

from datetime import datetime

import pytest
from openpyxl import Workbook

import dbgpt.util.file_client as file_client
from dbgpt_app.scene.chat_data.chat_excel.excel_reader import ExcelReader


@pytest.fixture
def read_workbook(tmp_path, monkeypatch):
    monkeypatch.setattr(
        file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(tmp_path.resolve())
    )
    readers = []

    def read(headers, values):
        path = tmp_path / f"headers-{len(readers)}.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        sheet.append(values)
        workbook.save(path)
        workbook.close()
        reader = ExcelReader("typed-headers", str(path))
        readers.append(reader)
        return reader

    yield read
    for reader in readers:
        reader.close()


@pytest.mark.parametrize(
    "headers, expected_names",
    [
        ([2024, 2023], ["2024", "2023"]),
        ([1.5, 2.5], ["1.5", "2.5"]),
        ([True, False], ["True", "False"]),
        (
            [datetime(2024, 1, 1), datetime(2023, 1, 1)],
            ["2024-01-01_00:00:00", "2023-01-01_00:00:00"],
        ),
        ([2024, "2024"], ["2024", "2024_1"]),
        ([None, "amount"], ["Unnamed:_0", "amount"]),
        (["", "amount"], ["Unnamed:_0", "amount"]),
        ([" ", "amount"], ["C0", "amount"]),
        (["Unnamed rate", "amount"], ["Unnamed_rate", "amount"]),
        ([" 指标 ", "total sales"], ["指标", "total_sales"]),
    ],
)
def test_workbook_header_types_keep_values(read_workbook, headers, expected_names):
    reader = read_workbook(headers, [10, 20])
    relation = reader.db.table("temp_table")
    assert relation.columns == expected_names
    assert relation.fetchall() == [(10, 20)]


def test_empty_unnamed_column_is_still_dropped(read_workbook):
    reader = read_workbook(["指标", None, 2024], ["GDP", None, 10])
    relation = reader.db.table("temp_table")
    assert relation.columns == ["指标", "2024"]
    assert relation.fetchall() == [("GDP", 10)]


def test_csv_text_headers_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(
        file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(tmp_path.resolve())
    )
    path = tmp_path / "headers.csv"
    path.write_text("year,total sales\n10,20\n", encoding="utf-8")
    reader = ExcelReader("text-headers", str(path))
    try:
        relation = reader.db.table("temp_table")
        assert relation.columns == ["year", "total_sales"]
        assert relation.fetchall() == [(10, 20)]
    finally:
        reader.close()
