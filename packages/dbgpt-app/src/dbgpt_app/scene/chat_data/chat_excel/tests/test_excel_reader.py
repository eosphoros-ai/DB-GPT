"""Roundtrip the schema advertised by Chat Excel through the real DuckDB parser."""

import duckdb
import pytest

import dbgpt.util.file_client as file_client
from dbgpt_app.scene.chat_data.chat_excel.excel_reader import ExcelReader


@pytest.fixture
def csv_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(file_client, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(tmp_path))
    path = tmp_path / "economic.csv"
    path.write_text(
        "指标,2024,2023\n国内生产总值,1349083.5,1294271.7\n", encoding="utf-8"
    )
    reader = ExcelReader("numeric-columns", str(path))
    try:
        yield reader
    finally:
        reader.close()


def test_numeric_csv_columns_have_executable_ddl(csv_reader):
    ddl = csv_reader.get_create_table_sql("temp_table")
    with duckdb.connect() as restored:
        restored.execute(ddl)
        assert restored.table("temp_table").columns == ["指标", "2024", "2023"]
    assert csv_reader.run('SELECT "2024", "2023" FROM temp_table', "temp_table")[1] == [
        (1349083.5, 1294271.7)
    ]


def test_numeric_sql_literal_remains_a_literal(csv_reader):
    assert csv_reader.run("SELECT 2024 FROM temp_table", "temp_table")[1] == [(2024,)]


@pytest.mark.parametrize(
    "column_name, table_name, quoted_column, quoted_table",
    [
        ("2024", "source", '"2024"', '"source"'),
        ("amount", "source", '"amount"', '"source"'),
        ("total sales", "source table", '"total sales"', '"source table"'),
        ("from", "select", '"from"', '"select"'),
        ('gross"amount', 'source"table', '"gross""amount"', '"source""table"'),
    ],
    ids=["numeric", "normal", "space", "keyword", "embedded-quote"],
)
def test_existing_table_schema_preserves_identifiers_and_values(
    tmp_path, column_name, table_name, quoted_column, quoted_table
):
    database = tmp_path / "source.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute(f"CREATE TABLE {quoted_table} ({quoted_column} INTEGER)")
        connection.execute(f"INSERT INTO {quoted_table} VALUES (?)", [37])

    reader = ExcelReader(
        "existing-table",
        "unused.csv",
        database_name=str(database),
        table_name=table_name,
    )
    try:
        ddl = reader.get_create_table_sql(table_name)
        with duckdb.connect() as restored:
            restored.execute(ddl)
            assert restored.sql(f"SELECT * FROM {quoted_table}").columns == [
                column_name
            ]
            restored.execute(f"INSERT INTO {quoted_table} VALUES (?)", [37])
            assert restored.execute(
                f"SELECT {quoted_column} FROM {quoted_table}"
            ).fetchall() == [(37,)]
        assert reader.db.execute(
            f"SELECT {quoted_column} FROM {quoted_table}"
        ).fetchall() == [(37,)]
    finally:
        reader.close()
