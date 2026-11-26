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


def _build_full_demo(output: Path) -> None:
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


def build_simple_demo(source: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {output}")
    if not source.is_file():
        raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    source_db = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True)
    output_db = sqlite3.connect(output)
    try:
        orders = source_db.execute(
            """SELECT o.order_id, substr(o.order_purchase_timestamp,1,10),
                   c.customer_state, SUM(i.price), SUM(i.freight_value),
                   julianday(o.order_delivered_customer_date)
                       - julianday(o.order_purchase_timestamp),
                   CASE WHEN o.order_delivered_customer_date IS NULL
                             OR o.order_estimated_delivery_date IS NULL
                        THEN NULL WHEN o.order_delivered_customer_date
                             <= o.order_estimated_delivery_date
                        THEN 1 ELSE 0 END,
                   (SELECT AVG(r.review_score) FROM order_reviews r
                    WHERE r.order_id=o.order_id)
               FROM orders o JOIN customers c ON c.customer_id=o.customer_id
               JOIN order_items i ON i.order_id=o.order_id
               WHERE o.order_status='delivered'
                 AND o.order_purchase_timestamp >= '2017-01-01'
                 AND o.order_purchase_timestamp < '2018-09-01'
               GROUP BY o.order_id"""
        ).fetchall()
        items = source_db.execute(
            """SELECT i.order_id,
                      COALESCE(t.product_category_name_english,
                               p.product_category_name,'unmapped'), i.price
               FROM order_items i JOIN orders o ON o.order_id=i.order_id
               LEFT JOIN products p ON p.product_id=i.product_id
               LEFT JOIN product_category_translation t
                   ON t.product_category_name=p.product_category_name
               WHERE o.order_status='delivered'
                 AND o.order_purchase_timestamp >= '2017-01-01'
                 AND o.order_purchase_timestamp < '2018-09-01'"""
        ).fetchall()
        output_db.executescript(
            """CREATE TABLE demo_orders(order_id TEXT PRIMARY KEY,
               purchase_date TEXT NOT NULL,
               customer_state TEXT, product_gmv REAL NOT NULL, freight REAL NOT NULL,
               delivery_days REAL, on_time INTEGER, review_score REAL);
               CREATE TABLE demo_items(order_id TEXT NOT NULL,
               category TEXT NOT NULL, price REAL NOT NULL,
               FOREIGN KEY(order_id) REFERENCES demo_orders(order_id));
               CREATE INDEX demo_items_order ON demo_items(order_id);"""
        )
        output_db.executemany(
            "INSERT INTO demo_orders VALUES (?,?,?,?,?,?,?,?)", orders
        )
        output_db.executemany("INSERT INTO demo_items VALUES (?,?,?)", items)
        output_db.commit()
    finally:
        source_db.close()
        output_db.close()


def build_demo(output: Path, source: Path | None = None) -> None:
    """Build the two-table demo, optionally from an existing Olist database."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {output}")
    if source is not None:
        if source.resolve() == output.resolve():
            raise ValueError("Source and output must be different paths")
        build_simple_demo(source, output)
        return
    with tempfile.TemporaryDirectory(prefix="olist-demo-source-") as temporary:
        generated_source = Path(temporary) / "olist.db"
        _build_full_demo(generated_source)
        build_simple_demo(generated_source, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parents[2] / "pilot/examples/Olist_Ecommerce.db",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Optional existing Olist SQLite source; the source is never modified",
    )
    args = parser.parse_args()
    build_demo(args.output, args.source)
