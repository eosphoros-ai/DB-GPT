"""Load the same Olist CSV files into SQLite or MySQL.

The loader uses one SQLAlchemy schema and one conversion path for both engines.
That keeps the demo focused on database portability instead of maintaining two
quietly different datasets.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent
metadata = MetaData()

customers = Table(
    "olist_customers",
    metadata,
    Column("customer_id", String(32), primary_key=True),
    Column("customer_unique_id", String(32), nullable=False),
    Column("customer_zip_code_prefix", Integer, nullable=False),
    Column("customer_city", String(128), nullable=False),
    Column("customer_state", String(2), nullable=False),
    Index("ix_olist_customers_unique", "customer_unique_id"),
    Index("ix_olist_customers_state", "customer_state"),
)

products = Table(
    "olist_products",
    metadata,
    Column("product_id", String(32), primary_key=True),
    Column("product_category_name", String(128)),
    Column("product_name_length", Integer),
    Column("product_description_length", Integer),
    Column("product_photos_qty", Integer),
    Column("product_weight_g", Float),
    Column("product_length_cm", Float),
    Column("product_height_cm", Float),
    Column("product_width_cm", Float),
    Index("ix_olist_products_category", "product_category_name"),
)

sellers = Table(
    "olist_sellers",
    metadata,
    Column("seller_id", String(32), primary_key=True),
    Column("seller_zip_code_prefix", Integer, nullable=False),
    Column("seller_city", String(128), nullable=False),
    Column("seller_state", String(2), nullable=False),
    Index("ix_olist_sellers_state", "seller_state"),
)

category_translation = Table(
    "olist_category_translation",
    metadata,
    Column("product_category_name", String(128), primary_key=True),
    Column("product_category_name_english", String(128), nullable=False),
)

orders = Table(
    "olist_orders",
    metadata,
    Column("order_id", String(32), primary_key=True),
    Column(
        "customer_id",
        String(32),
        ForeignKey("olist_customers.customer_id"),
        nullable=False,
    ),
    Column("order_status", String(32), nullable=False),
    Column("order_purchase_timestamp", DateTime, nullable=False),
    Column("order_approved_at", DateTime),
    Column("order_delivered_carrier_date", DateTime),
    Column("order_delivered_customer_date", DateTime),
    Column("order_estimated_delivery_date", DateTime, nullable=False),
    Index("ix_olist_orders_purchase", "order_purchase_timestamp"),
    Index("ix_olist_orders_status", "order_status"),
)

order_items = Table(
    "olist_order_items",
    metadata,
    Column(
        "order_id",
        String(32),
        ForeignKey("olist_orders.order_id"),
        primary_key=True,
    ),
    Column("order_item_id", Integer, primary_key=True),
    Column(
        "product_id",
        String(32),
        ForeignKey("olist_products.product_id"),
        nullable=False,
    ),
    Column(
        "seller_id",
        String(32),
        ForeignKey("olist_sellers.seller_id"),
        nullable=False,
    ),
    Column("shipping_limit_date", DateTime, nullable=False),
    Column("price", Float, nullable=False),
    Column("freight_value", Float, nullable=False),
    Index("ix_olist_items_product", "product_id"),
    Index("ix_olist_items_seller", "seller_id"),
)

payments = Table(
    "olist_order_payments",
    metadata,
    Column(
        "order_id",
        String(32),
        ForeignKey("olist_orders.order_id"),
        primary_key=True,
    ),
    Column("payment_sequential", Integer, primary_key=True),
    Column("payment_type", String(32), nullable=False),
    Column("payment_installments", Integer, nullable=False),
    Column("payment_value", Float, nullable=False),
    Index("ix_olist_payments_type", "payment_type"),
)

reviews = Table(
    "olist_order_reviews",
    metadata,
    Column("review_id", String(32), primary_key=True),
    Column(
        "order_id",
        String(32),
        ForeignKey("olist_orders.order_id"),
        primary_key=True,
    ),
    Column("review_score", Integer, nullable=False),
    Column("review_comment_title", Text),
    Column("review_comment_message", Text),
    Column("review_creation_date", DateTime, nullable=False),
    Column("review_answer_timestamp", DateTime, nullable=False),
    Index("ix_olist_reviews_order", "order_id"),
    Index("ix_olist_reviews_score", "review_score"),
)

geolocation = Table(
    "olist_geolocation",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("geolocation_zip_code_prefix", Integer, nullable=False),
    Column("geolocation_lat", Float, nullable=False),
    Column("geolocation_lng", Float, nullable=False),
    Column("geolocation_city", String(128), nullable=False),
    Column("geolocation_state", String(2), nullable=False),
    Index("ix_olist_geo_zip", "geolocation_zip_code_prefix"),
)


def _optional(converter: Callable[[str], Any]) -> Callable[[str], Any]:
    def convert(value: str) -> Any:
        return None if value == "" else converter(value)

    return convert


def _text(value: str) -> str:
    return value


def _integer(value: str) -> int:
    return int(float(value))


def _number(value: str) -> float:
    return float(value)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class CsvSpec:
    filename: str
    table: Table
    converters: dict[str, Callable[[str], Any]]
    optional: bool = False


CORE_SPECS = (
    CsvSpec(
        "olist_customers_dataset.csv",
        customers,
        {
            "customer_id": _text,
            "customer_unique_id": _text,
            "customer_zip_code_prefix": _integer,
            "customer_city": _text,
            "customer_state": _text,
        },
    ),
    CsvSpec(
        "olist_products_dataset.csv",
        products,
        {
            "product_id": _text,
            "product_category_name": _optional(_text),
            "product_name_lenght": _optional(_integer),
            "product_description_lenght": _optional(_integer),
            "product_photos_qty": _optional(_integer),
            "product_weight_g": _optional(_number),
            "product_length_cm": _optional(_number),
            "product_height_cm": _optional(_number),
            "product_width_cm": _optional(_number),
        },
    ),
    CsvSpec(
        "olist_sellers_dataset.csv",
        sellers,
        {
            "seller_id": _text,
            "seller_zip_code_prefix": _integer,
            "seller_city": _text,
            "seller_state": _text,
        },
    ),
    CsvSpec(
        "product_category_name_translation.csv",
        category_translation,
        {
            "product_category_name": _text,
            "product_category_name_english": _text,
        },
    ),
    CsvSpec(
        "olist_orders_dataset.csv",
        orders,
        {
            "order_id": _text,
            "customer_id": _text,
            "order_status": _text,
            "order_purchase_timestamp": _timestamp,
            "order_approved_at": _optional(_timestamp),
            "order_delivered_carrier_date": _optional(_timestamp),
            "order_delivered_customer_date": _optional(_timestamp),
            "order_estimated_delivery_date": _timestamp,
        },
    ),
    CsvSpec(
        "olist_order_items_dataset.csv",
        order_items,
        {
            "order_id": _text,
            "order_item_id": _integer,
            "product_id": _text,
            "seller_id": _text,
            "shipping_limit_date": _timestamp,
            "price": _number,
            "freight_value": _number,
        },
    ),
    CsvSpec(
        "olist_order_payments_dataset.csv",
        payments,
        {
            "order_id": _text,
            "payment_sequential": _integer,
            "payment_type": _text,
            "payment_installments": _integer,
            "payment_value": _number,
        },
    ),
    CsvSpec(
        "olist_order_reviews_dataset.csv",
        reviews,
        {
            "review_id": _text,
            "order_id": _text,
            "review_score": _integer,
            "review_comment_title": _optional(_text),
            "review_comment_message": _optional(_text),
            "review_creation_date": _timestamp,
            "review_answer_timestamp": _timestamp,
        },
    ),
)

GEOLOCATION_SPEC = CsvSpec(
    "olist_geolocation_dataset.csv",
    geolocation,
    {
        "geolocation_zip_code_prefix": _integer,
        "geolocation_lat": _number,
        "geolocation_lng": _number,
        "geolocation_city": _text,
        "geolocation_state": _text,
    },
    optional=True,
)

CSV_RENAMES = {
    "product_name_lenght": "product_name_length",
    "product_description_lenght": "product_description_length",
}


def _records(spec: CsvSpec, path: Path) -> Iterator[dict[str, Any]]:
    # ``utf-8-sig`` accepts ordinary UTF-8 files and strips the optional BOM
    # used by Olist's category translation CSV.  Without it the first header
    # becomes ``\ufeffproduct_category_name`` and an otherwise valid official
    # dataset fails the strict column check below.
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        actual = set(reader.fieldnames or [])
        expected = set(spec.converters)
        if actual != expected:
            raise ValueError(
                f"Unexpected columns in {path.name}: expected {sorted(expected)}, "
                f"got {sorted(actual)}"
            )
        for row in reader:
            converted = {
                CSV_RENAMES.get(name, name): converter(row[name])
                for name, converter in spec.converters.items()
            }
            yield converted


def _chunks(records: Iterator[dict[str, Any]], size: int):
    chunk: list[dict[str, Any]] = []
    for record in records:
        chunk.append(record)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _engine(url: str) -> Engine:
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def load_dataset(
    engine: Engine,
    source_dir: Path,
    *,
    include_geolocation: bool = False,
    replace: bool = False,
    chunk_size: int = 2000,
) -> dict[str, int]:
    specs = list(CORE_SPECS)
    if include_geolocation:
        specs.append(GEOLOCATION_SPEC)
    missing = [
        spec.filename for spec in specs if not (source_dir / spec.filename).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Missing Olist CSV files: {', '.join(missing)}")

    if replace:
        metadata.drop_all(engine, tables=[spec.table for spec in reversed(specs)])
    metadata.create_all(engine, tables=[spec.table for spec in specs])

    counts: dict[str, int] = {}
    for spec in specs:
        inserted = 0
        with engine.begin() as connection:
            if not replace:
                existing = connection.scalar(
                    select(func.count()).select_from(spec.table)
                )
                if existing:
                    raise ValueError(
                        f"Table {spec.table.name} already contains {existing} rows; "
                        "use --replace to rebuild it"
                    )
            for chunk in _chunks(
                _records(spec, source_dir / spec.filename), chunk_size
            ):
                connection.execute(spec.table.insert(), chunk)
                inserted += len(chunk)
        counts[spec.table.name] = inserted
        print(f"Loaded {inserted:>8,} rows into {spec.table.name}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--sqlite", type=Path)
    destination.add_argument("--mysql-url")
    parser.add_argument("--include-geolocation", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=2000)
    args = parser.parse_args()

    if args.sqlite:
        args.sqlite.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{args.sqlite.resolve().as_posix()}"
    else:
        url = args.mysql_url
    engine = _engine(url)
    try:
        load_dataset(
            engine,
            args.source_dir.resolve(),
            include_geolocation=args.include_geolocation,
            replace=args.replace,
            chunk_size=args.chunk_size,
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
