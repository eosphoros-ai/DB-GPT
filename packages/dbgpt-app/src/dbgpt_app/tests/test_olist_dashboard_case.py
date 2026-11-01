import csv
import json
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, select

from dbgpt_app.openapi.api_v1.dashboard.schemas import DashboardSchemaV1
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from examples.dashboard.olist.gold_queries import execute_gold_queries
from examples.dashboard.olist.load_olist import (
    CORE_SPECS,
    customers,
    load_dataset,
)


def _repository_root() -> Path:
    return next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / ".git").exists()
    )


class _SQLiteConnector:
    db_type = "sqlite"

    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)

    def get_table_names(self):
        return [
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]

    def get_fields(self, table, database=None):
        return [
            (row[1], row[2])
            for row in self.connection.execute(f"PRAGMA table_info({table})")
        ]

    def query_ex(self, sql, params=None, timeout=None):
        cursor = self.connection.execute(sql, params or {})
        return [item[0] for item in cursor.description], cursor.fetchall()


def _write_csv(
    source_dir: Path,
    filename: str,
    fieldnames: list[str],
    rows: list[dict],
    *,
    bom: bool = False,
) -> None:
    encoding = "utf-8-sig" if bom else "utf-8"
    with (source_dir / filename).open("w", encoding=encoding, newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _synthetic_source(source_dir: Path) -> None:
    source_dir.mkdir()
    _write_csv(
        source_dir,
        "olist_customers_dataset.csv",
        [
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ],
        [
            {
                "customer_id": "c1",
                "customer_unique_id": "u1",
                "customer_zip_code_prefix": 1000,
                "customer_city": "sao paulo",
                "customer_state": "SP",
            },
            {
                "customer_id": "c2",
                "customer_unique_id": "u2",
                "customer_zip_code_prefix": 2000,
                "customer_city": "rio",
                "customer_state": "RJ",
            },
        ],
    )
    _write_csv(
        source_dir,
        "olist_products_dataset.csv",
        [
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ],
        [
            {
                "product_id": "p1",
                "product_category_name": "beleza",
                "product_name_lenght": 10,
                "product_description_lenght": 20,
                "product_photos_qty": 1,
                "product_weight_g": 100,
                "product_length_cm": 10,
                "product_height_cm": 10,
                "product_width_cm": 10,
            },
            {
                "product_id": "p2",
                "product_category_name": "livros",
                "product_name_lenght": "",
                "product_description_lenght": "",
                "product_photos_qty": "",
                "product_weight_g": "",
                "product_length_cm": "",
                "product_height_cm": "",
                "product_width_cm": "",
            },
        ],
    )
    _write_csv(
        source_dir,
        "olist_sellers_dataset.csv",
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        [
            {
                "seller_id": "s1",
                "seller_zip_code_prefix": 1000,
                "seller_city": "sao paulo",
                "seller_state": "SP",
            }
        ],
    )
    # The official translation file contains a BOM.  This fixture preserves it
    # so a regression in the loader's header decoding is caught automatically.
    _write_csv(
        source_dir,
        "product_category_name_translation.csv",
        ["product_category_name", "product_category_name_english"],
        [
            {
                "product_category_name": "beleza",
                "product_category_name_english": "beauty",
            },
            {
                "product_category_name": "livros",
                "product_category_name_english": "books",
            },
        ],
        bom=True,
    )
    _write_csv(
        source_dir,
        "olist_orders_dataset.csv",
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        [
            {
                "order_id": "o1",
                "customer_id": "c1",
                "order_status": "delivered",
                "order_purchase_timestamp": "2018-01-01 00:00:00",
                "order_approved_at": "2018-01-01 01:00:00",
                "order_delivered_carrier_date": "2018-01-02 00:00:00",
                "order_delivered_customer_date": "2018-01-06 00:00:00",
                "order_estimated_delivery_date": "2018-01-05 00:00:00",
            },
            {
                "order_id": "o2",
                "customer_id": "c2",
                "order_status": "delivered",
                "order_purchase_timestamp": "2018-02-01 00:00:00",
                "order_approved_at": "",
                "order_delivered_carrier_date": "",
                "order_delivered_customer_date": "2018-02-03 00:00:00",
                "order_estimated_delivery_date": "2018-02-05 00:00:00",
            },
        ],
    )
    _write_csv(
        source_dir,
        "olist_order_items_dataset.csv",
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ],
        [
            {
                "order_id": "o1",
                "order_item_id": 1,
                "product_id": "p1",
                "seller_id": "s1",
                "shipping_limit_date": "2018-01-03 00:00:00",
                "price": 10,
                "freight_value": 1,
            },
            {
                "order_id": "o1",
                "order_item_id": 2,
                "product_id": "p2",
                "seller_id": "s1",
                "shipping_limit_date": "2018-01-03 00:00:00",
                "price": 20,
                "freight_value": 2,
            },
            {
                "order_id": "o2",
                "order_item_id": 1,
                "product_id": "p1",
                "seller_id": "s1",
                "shipping_limit_date": "2018-02-02 00:00:00",
                "price": 30,
                "freight_value": 3,
            },
        ],
    )
    _write_csv(
        source_dir,
        "olist_order_payments_dataset.csv",
        [
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ],
        [
            {
                "order_id": "o1",
                "payment_sequential": 1,
                "payment_type": "voucher",
                "payment_installments": 1,
                "payment_value": 5,
            },
            {
                "order_id": "o1",
                "payment_sequential": 2,
                "payment_type": "credit_card",
                "payment_installments": 1,
                "payment_value": 25,
            },
            {
                "order_id": "o2",
                "payment_sequential": 1,
                "payment_type": "credit_card",
                "payment_installments": 1,
                "payment_value": 30,
            },
        ],
    )
    _write_csv(
        source_dir,
        "olist_order_reviews_dataset.csv",
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ],
        [
            {
                "review_id": "r1",
                "order_id": "o1",
                "review_score": 1,
                "review_comment_title": "late",
                "review_comment_message": "late order",
                "review_creation_date": "2018-01-07 00:00:00",
                "review_answer_timestamp": "2018-01-08 00:00:00",
            },
            {
                "review_id": "r2",
                "order_id": "o2",
                "review_score": 5,
                "review_comment_title": "",
                "review_comment_message": "",
                "review_creation_date": "2018-02-04 00:00:00",
                "review_answer_timestamp": "2018-02-05 00:00:00",
            },
        ],
    )


def test_loader_accepts_official_bom_and_converts_all_core_tables(tmp_path):
    source_dir = tmp_path / "csv"
    _synthetic_source(source_dir)
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'olist.db').as_posix()}", future=True
    )
    try:
        counts = load_dataset(engine, source_dir, replace=True, chunk_size=1)
        assert set(counts) == {spec.table.name for spec in CORE_SPECS}
        assert counts["olist_orders"] == 2
        assert counts["olist_order_items"] == 3
        assert counts["olist_order_payments"] == 3
        with engine.connect() as connection:
            assert connection.scalar(select(customers.c.customer_id).limit(1)) == "c1"
    finally:
        engine.dispose()


def test_gold_queries_do_not_multiply_split_payments_by_order_items(tmp_path):
    source_dir = tmp_path / "csv"
    _synthetic_source(source_dir)
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'olist.db').as_posix()}", future=True
    )
    try:
        load_dataset(engine, source_dir, replace=True)
        answers = execute_gold_queries(engine)
    finally:
        engine.dispose()

    assert answers["overview"] == [
        {
            "order_count": 2,
            "delivered_orders": 2,
            "unique_customers": 2,
            "payment_total": 60.0,
        }
    ]
    assert answers["top_categories"][:2] == [
        {"category": "beauty", "order_count": 2, "item_revenue": 40.0},
        {"category": "books", "order_count": 1, "item_revenue": 20.0},
    ]
    assert answers["delivery_quality"] == [
        {
            "delivered_orders": 2,
            "avg_delivery_days": 3.5,
            "late_orders": 1,
            "late_rate_pct": 50.0,
        }
    ]


def test_mysql_query_variant_uses_timestampdiff_for_date_math():
    from examples.dashboard.olist.gold_queries import GOLD_QUERIES

    delivery = next(query for query in GOLD_QUERIES if query.name == "delivery_quality")
    assert "JULIANDAY" in delivery.for_dialect("sqlite")
    assert "TIMESTAMPDIFF" in delivery.for_dialect("mysql")


def test_olist_dashboard_schema_executes_all_widgets_on_relational_data(tmp_path):
    source_dir = tmp_path / "csv"
    database_path = tmp_path / "olist.db"
    _synthetic_source(source_dir)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}", future=True)
    try:
        load_dataset(engine, source_dir, replace=True)
    finally:
        engine.dispose()

    schema_path = (
        _repository_root()
        / "examples"
        / "dashboard"
        / "schemas"
        / "olist-ecommerce.schema.json"
    )
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    # Keep the fixture filter values small while retaining the production
    # schema's field mappings and query contracts.
    state_filter = next(
        item for item in payload["filters"] if item["id"] == "customer-states"
    )
    state_filter["default"] = ["SP", "RJ"]
    schema = DashboardSchemaV1.model_validate(payload)
    connector = _SQLiteConnector(database_path)
    service = DashboardService(dao=object(), connector_resolver=lambda _: connector)
    try:
        result = service.validate_schema(schema, execute_queries=True)
    finally:
        connector.connection.close()

    assert result.valid, [issue.model_dump() for issue in result.issues]
    assert set(result.widget_status.values()) == {"executed"}
