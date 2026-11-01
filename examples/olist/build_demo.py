"""Generate the bundled Olist-shaped synthetic database without downloading data."""

import argparse
import csv
import hashlib
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from build_olist_sqlite import TABLES, build_database


def _identifier(kind: str, index: int) -> str:
    return hashlib.sha256(f"olist-demo:{kind}:{index}".encode()).hexdigest()[:32]


def build_demo(output: Path) -> None:
    """Use the real importer and schema with deterministic, invented observations."""
    rows = {spec.table_name: [] for spec in TABLES}
    regions = (
        ("SP", "sao paulo", 1000, -23.55, -46.63),
        ("RJ", "rio de janeiro", 20000, -22.90, -43.20),
        ("MG", "belo horizonte", 30000, -19.93, -43.94),
        ("PR", "curitiba", 80000, -25.43, -49.27),
    )
    categories = (
        ("beleza_saude", "health_beauty"),
        ("cama_mesa_banho", "bed_bath_table"),
        ("esporte_lazer", "sports_leisure"),
        ("informatica_acessorios", "computers_accessories"),
    )
    for index, (category, english) in enumerate(categories):
        rows["product_category_translation"].append((category, english))
        rows["products"].append(
            (_identifier("product", index), category, 30, 100, 1, 500, 20, 10, 15)
        )
    for index, (state, city, zipcode, latitude, longitude) in enumerate(regions):
        rows["sellers"].append((_identifier("seller", index), zipcode, city, state))
        rows["geolocation"].append((zipcode, latitude, longitude, city, state))
    order_index = 0
    for month in range(20):
        year, month_number = 2017 + month // 12, month % 12 + 1
        for number in range(24 + month % 12 * 2):
            index = order_index
            order_index += 1
            order_id, customer_id = (
                _identifier("order", index),
                _identifier("customer", index),
            )
            state, city, zipcode, _, _ = regions[index % len(regions)]
            rows["customers"].append(
                (customer_id, _identifier("person", index % 180), zipcode, city, state)
            )
            purchase = datetime(year, month_number, number % 28 + 1, 10)
            late = index % 7 == 0
            delivery = purchase + timedelta(days=20 if late else 5 + index % 8)
            delivered = index % 19 != 0
            rows["orders"].append(
                (
                    order_id,
                    customer_id,
                    "delivered" if delivered else "canceled",
                    purchase.isoformat(sep=" "),
                    (purchase + timedelta(hours=2)).isoformat(sep=" "),
                    (purchase + timedelta(days=2)).isoformat(sep=" ")
                    if delivered
                    else "",
                    delivery.isoformat(sep=" ") if delivered else "",
                    (purchase + timedelta(days=15)).isoformat(sep=" "),
                )
            )
            if not delivered:
                continue
            total = 0
            for item in range(1, 3 if index % 5 == 0 else 2):
                product = (index + item) % len(categories)
                price = 45 + product * 30 + index % 17 * 2
                freight = 8 + index % 9
                rows["order_items"].append(
                    (
                        order_id,
                        item,
                        _identifier("product", product),
                        _identifier("seller", index % len(regions)),
                        (purchase + timedelta(days=3)).isoformat(sep=" "),
                        price,
                        freight,
                    )
                )
                total += price + freight
            split = index % 11 == 0
            rows["order_payments"].append(
                (
                    order_id,
                    1,
                    "credit_card" if index % 3 else "boleto",
                    1 + index % 6 if index % 3 else 1,
                    total - 10 if split else total,
                )
            )
            if split:
                rows["order_payments"].append((order_id, 2, "voucher", 1, 10))
            if index % 13:
                rows["order_reviews"].append(
                    (
                        _identifier("review", index),
                        order_id,
                        2 if late else 4 + index % 2,
                        "Synthetic review",
                        "Invented for the offline example",
                        (delivery + timedelta(days=1)).isoformat(sep=" "),
                        (delivery + timedelta(days=2)).isoformat(sep=" "),
                    )
                )
    with tempfile.TemporaryDirectory(prefix="olist-demo-") as temporary:
        csv_dir = Path(temporary)
        for spec in TABLES:
            with (csv_dir / spec.source_file).open(
                "w", encoding="utf-8", newline=""
            ) as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(spec.columns)
                writer.writerows(rows[spec.table_name])
        build_database(csv_dir, output)
    governance = Path(__file__).with_name("olist-analytics-metric-governance.md")
    with sqlite3.connect(output) as connection:
        connection.execute(
            "CREATE TABLE dataset_metadata (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.executemany(
            "INSERT INTO dataset_metadata VALUES (?, ?)",
            [
                ("dataset_kind", "synthetic_demo"),
                ("generator", "examples/olist/build_demo.py"),
                ("notice", "Invented observations; not real Olist transactions"),
                ("currency", "BRL"),
                ("license", "MIT"),
            ],
        )
        connection.execute("CREATE TABLE metric_definitions (document TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO metric_definitions VALUES (?)",
            (governance.read_text(encoding="utf-8"),),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[2] / "pilot/examples/Olist_Ecommerce.db",
    )
    build_demo(parser.parse_args().output)
