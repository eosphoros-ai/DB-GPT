import csv
import importlib.util
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "walmart_source", ROOT / "examples/dashboard/verify_walmart_source.py"
)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_walmart_fingerprint_is_checkout_independent(tmp_path, newline):
    original = ROOT / "docker/examples/excel/Walmart_Sales.csv"
    csv_path = tmp_path / "sales.csv"
    csv_path.write_bytes(
        original.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
    )
    database = tmp_path / "sales.db"
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE walmart_sales (Store INTEGER, Date TEXT, Weekly_Sales REAL, "
            "Holiday_Flag INTEGER, Temperature REAL, Fuel_Price REAL, CPI REAL, "
            "Unemployment REAL)"
        )
        connection.executemany(
            "INSERT INTO walmart_sales VALUES (?,?,?,?,?,?,?,?)",
            [tuple(row[field] for field in source.FIELDS) for row in rows],
        )
    assert source.verify(csv_path, database)["rows_compared"] == 6435
    csv_path.write_bytes(csv_path.read_bytes().replace(b"1643690.9", b"1643690.8", 1))
    with pytest.raises(ValueError, match="fingerprint"):
        source.verify(csv_path, database)
