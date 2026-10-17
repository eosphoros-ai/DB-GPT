"""Build a reproducible SQLite datasource from the public Olist CSV files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence


@dataclass(frozen=True)
class TableSpec:
    source_file: str
    table_name: str
    columns: Sequence[str]
    integer_columns: frozenset[str] = frozenset()
    real_columns: frozenset[str] = frozenset()


TABLES = (
    TableSpec(
        "olist_customers_dataset.csv",
        "customers",
        (
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ),
        integer_columns=frozenset({"customer_zip_code_prefix"}),
    ),
    TableSpec(
        "olist_geolocation_dataset.csv",
        "geolocation",
        (
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ),
        integer_columns=frozenset({"geolocation_zip_code_prefix"}),
        real_columns=frozenset({"geolocation_lat", "geolocation_lng"}),
    ),
    TableSpec(
        "olist_order_items_dataset.csv",
        "order_items",
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ),
        integer_columns=frozenset({"order_item_id"}),
        real_columns=frozenset({"price", "freight_value"}),
    ),
    TableSpec(
        "olist_order_payments_dataset.csv",
        "order_payments",
        (
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ),
        integer_columns=frozenset({"payment_sequential", "payment_installments"}),
        real_columns=frozenset({"payment_value"}),
    ),
    TableSpec(
        "olist_order_reviews_dataset.csv",
        "order_reviews",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
        integer_columns=frozenset({"review_score"}),
    ),
    TableSpec(
        "olist_orders_dataset.csv",
        "orders",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
    ),
    TableSpec(
        "olist_products_dataset.csv",
        "products",
        (
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        integer_columns=frozenset(
            {
                "product_name_lenght",
                "product_description_lenght",
                "product_photos_qty",
            }
        ),
        real_columns=frozenset(
            {
                "product_weight_g",
                "product_length_cm",
                "product_height_cm",
                "product_width_cm",
            }
        ),
    ),
    TableSpec(
        "olist_sellers_dataset.csv",
        "sellers",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
        integer_columns=frozenset({"seller_zip_code_prefix"}),
    ),
    TableSpec(
        "product_category_name_translation.csv",
        "product_category_translation",
        ("product_category_name", "product_category_name_english"),
    ),
)

JOIN_INDEXES = (
    ("orders", "order_id"),
    ("orders", "customer_id"),
    ("customers", "customer_id"),
    ("products", "product_id"),
    ("sellers", "seller_id"),
    ("product_category_translation", "product_category_name"),
    ("order_items", "order_id"),
    ("order_items", "product_id"),
    ("order_items", "seller_id"),
    ("order_payments", "order_id"),
    ("order_reviews", "order_id"),
)


def _column_type(spec: TableSpec, column: str) -> str:
    if column in spec.integer_columns:
        return "INTEGER"
    if column in spec.real_columns:
        return "REAL"
    return "TEXT"


def _converter(spec: TableSpec, column: str) -> Callable[[str], object]:
    if column in spec.integer_columns:
        return int
    if column in spec.real_columns:
        return float
    return str


def _convert(value: Optional[str], converter: Callable[[str], object]) -> object:
    if value is None or value == "":
        return None
    return converter(value)


def _rows(path: Path, spec: TableSpec) -> Iterable[Sequence[object]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != tuple(spec.columns):
            raise ValueError(
                f"Unexpected columns in {path.name}: {reader.fieldnames!r}"
            )
        converters = [_converter(spec, column) for column in spec.columns]
        for row in reader:
            yield tuple(
                _convert(row[column], converter)
                for column, converter in zip(spec.columns, converters)
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_database(csv_dir: Path, output: Path) -> Dict[str, int]:
    """Import all required Olist files and return table row counts."""
    csv_dir = csv_dir.resolve()
    output = output.resolve()
    missing = [
        spec.source_file
        for spec in TABLES
        if not (csv_dir / spec.source_file).is_file()
    ]
    if missing:
        raise FileNotFoundError("Missing required Olist files: " + ", ".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    counts: Dict[str, int] = {}
    try:
        with closing(sqlite3.connect(temporary)) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE _olist_import_manifest (
                    source_file TEXT PRIMARY KEY,
                    table_name TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                    )"""
                )
                for spec in TABLES:
                    definitions = ", ".join(
                        f'"{column}" {_column_type(spec, column)}'
                        for column in spec.columns
                    )
                    connection.execute(
                        f'CREATE TABLE "{spec.table_name}" ({definitions})'
                    )
                    placeholders = ", ".join("?" for _ in spec.columns)
                    connection.executemany(
                        f'INSERT INTO "{spec.table_name}" VALUES ({placeholders})',
                        _rows(csv_dir / spec.source_file, spec),
                    )
                    row_count = connection.execute(
                        f'SELECT COUNT(*) FROM "{spec.table_name}"'
                    ).fetchone()[0]
                    counts[spec.table_name] = row_count
                    connection.execute(
                        "INSERT INTO _olist_import_manifest VALUES (?, ?, ?, ?, ?)",
                        (
                            spec.source_file,
                            spec.table_name,
                            row_count,
                            _sha256(csv_dir / spec.source_file),
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                for table, column in JOIN_INDEXES:
                    connection.execute(
                        f'CREATE INDEX "idx_{table}_{column}" ON "{table}" ("{column}")'
                    )
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    counts = build_database(args.csv_dir, args.output)
    row_count = sum(counts.values())
    print(f"Built {args.output} with {row_count:,} rows in {len(counts)} tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
