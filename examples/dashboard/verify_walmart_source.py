"""Verify the bundled historical Walmart CSV and SQLite data independently."""

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_SHA256 = "0846b6941217dd938ceba6ae04650ccbbd01f4877a5f88bfa4dbecda54806c8f"
FIELDS = (
    "Store",
    "Date",
    "Weekly_Sales",
    "Holiday_Flag",
    "Temperature",
    "Fuel_Price",
    "CPI",
    "Unemployment",
)


def verify(csv_path: Path, database: Path) -> dict:
    """Compare all eight fields of every row; never write to the source database."""
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if digest != CSV_SHA256:
        raise ValueError(
            "CSV fingerprint differs from the documented historical dataset"
        )
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("Unexpected Walmart CSV columns")
        records = list(reader)
    rows = [
        (
            int(r["Store"]),
            r["Date"],
            float(r["Weekly_Sales"]),
            int(r["Holiday_Flag"]),
            *(float(r[f]) for f in FIELDS[4:]),
        )
        for r in records
    ]
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        saved = db.execute(
            "SELECT Store, Date, Weekly_Sales, Holiday_Flag, Temperature, "
            "Fuel_Price, CPI, Unemployment FROM walmart_sales"
        ).fetchall()
    if sorted(rows) != sorted(saved):
        raise ValueError("CSV and SQLite rows differ")
    if len(rows) != 6435 or len({r[:2] for r in rows}) != len(rows):
        raise ValueError("Unexpected row count or duplicate store/week keys")
    total = sum((Decimal(r["Weekly_Sales"]) for r in records), Decimal(0))
    if total != Decimal("6737218987.11"):
        raise ValueError("Unexpected sales total")
    dates = {datetime.strptime(r["Date"], "%d-%m-%Y").date() for r in records}
    return {
        "csv_sha256": digest,
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "rows_compared": len(rows),
        "fields_per_row": len(FIELDS),
        "stores": len({r[0] for r in rows}),
        "weeks": len(dates),
        "months": len({d.strftime("%Y-%m") for d in dates}),
        "date_range": [min(dates).isoformat(), max(dates).isoformat()],
        "weekly_sales_total": str(total),
        "public_matching_dataset": "https://www.kaggle.com/datasets/mikhail1681/walmart-sales",
        "result": "pass",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", type=Path, default=ROOT / "docker/examples/excel/Walmart_Sales.csv"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / "docker/examples/dashboard/Walmart_Sales.db",
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.csv, args.database), ensure_ascii=False, indent=2))
