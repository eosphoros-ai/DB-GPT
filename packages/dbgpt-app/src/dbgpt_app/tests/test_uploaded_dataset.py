import sqlite3
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.uploaded_dataset import materialize_uploaded_dataset


def _table_count(database_path: Path, table_name: str) -> int:
    with sqlite3.connect(database_path) as connection:
        return int(
            connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        )


def test_materialize_uploaded_dataset_preserves_tables_and_relationship_hints(
    tmp_path,
):
    orders_path = tmp_path / "orders.csv"
    customers_path = tmp_path / "customers.csv"
    orders_path.write_text(
        "order_id,customer_id,total\n1,10,5.5\n2,10,7.5\n3,20,8.0\n",
        encoding="utf-8",
    )
    customers_path.write_text(
        "customer_id,city\n10,Hangzhou\n20,Shanghai\n30,Beijing\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "dataset.sqlite"

    tables, relationships = materialize_uploaded_dataset(
        [str(orders_path), str(customers_path)], database_path
    )

    assert [table.table_name for table in tables] == ["orders", "customers"]
    assert [table.row_count for table in tables] == [3, 3]
    assert _table_count(database_path, "orders") == 3
    assert _table_count(database_path, "customers") == 3
    assert _table_count(database_path, "__dbgpt_dataset_manifest") == 2
    assert relationships == [
        {
            "column": "customer_id",
            "left_table": "orders",
            "right_table": "customers",
            "sample_distinct_overlap": 2,
            "status": "candidate_only",
        }
    ]
    assert _table_count(database_path, "__dbgpt_relationship_candidates") == 1


def test_materialize_uploaded_dataset_does_not_merge_same_stem_files(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_path = first_dir / "orders.csv"
    second_path = second_dir / "orders.csv"
    first_path.write_text("id,value\n1,a\n", encoding="utf-8")
    second_path.write_text("id,value\n2,b\n", encoding="utf-8")

    tables, _ = materialize_uploaded_dataset(
        [str(first_path), str(second_path)], tmp_path / "dataset.sqlite"
    )

    assert [table.table_name for table in tables] == ["orders", "orders_2"]


def test_materialize_uploaded_dataset_rejects_unsupported_files_and_cleans_db(
    tmp_path,
):
    source_path = tmp_path / "notes.txt"
    source_path.write_text("not tabular", encoding="utf-8")
    database_path = tmp_path / "dataset.sqlite"

    with pytest.raises(ValueError, match="Unsupported tabular file type"):
        materialize_uploaded_dataset([str(source_path)], database_path)

    assert not database_path.exists()


def test_materialize_uploaded_dataset_reads_gb18030_without_duplicate_rows(tmp_path):
    source_path = tmp_path / "customers.csv"
    source_path.write_bytes("customer_id,city\n1,杭州\n2,上海\n".encode("gb18030"))
    database_path = tmp_path / "dataset.sqlite"

    tables, _ = materialize_uploaded_dataset([str(source_path)], database_path)

    assert tables[0].row_count == 2
    assert _table_count(database_path, "customers") == 2


def test_materialize_uploaded_dataset_handles_wide_csv(tmp_path):
    source_path = tmp_path / "wide.csv"
    columns = [f"field_{index}" for index in range(1000)]
    source_path.write_text(
        ",".join(columns) + "\n" + ",".join("1" for _ in columns) + "\n",
        encoding="utf-8",
    )
    database_path = tmp_path / "dataset.sqlite"

    tables, _ = materialize_uploaded_dataset([str(source_path)], database_path)

    assert tables[0].row_count == 1
    assert len(tables[0].columns) == 1000
