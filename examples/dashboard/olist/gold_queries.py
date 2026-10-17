"""Auditable business queries for the Olist multi-table Dashboard case.

The query set deliberately aggregates payments per order before joining them
to orders or customers.  Joining payments and order items directly would form
a many-to-many multiplication for split payments and multi-item orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class GoldQuery:
    name: str
    sql: str
    mysql_sql: str | None = None

    def for_dialect(self, dialect: str) -> str:
        if dialect == "mysql" and self.mysql_sql:
            return self.mysql_sql
        return self.sql


PAYMENT_BY_ORDER = """
WITH payment_by_order AS (
    SELECT order_id, SUM(payment_value) AS payment_total
    FROM olist_order_payments
    GROUP BY order_id
)
"""

GOLD_QUERIES = (
    GoldQuery(
        "overview",
        PAYMENT_BY_ORDER
        + """
SELECT
    COUNT(*) AS order_count,
    SUM(CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END)
        AS delivered_orders,
    COUNT(DISTINCT c.customer_unique_id) AS unique_customers,
    ROUND(SUM(COALESCE(p.payment_total, 0)), 2) AS payment_total
FROM olist_orders AS o
JOIN olist_customers AS c ON c.customer_id = o.customer_id
LEFT JOIN payment_by_order AS p ON p.order_id = o.order_id
""",
    ),
    GoldQuery(
        "monthly_payments",
        PAYMENT_BY_ORDER
        + """
SELECT
    SUBSTR(o.order_purchase_timestamp, 1, 7) AS month,
    COUNT(*) AS order_count,
    ROUND(SUM(COALESCE(p.payment_total, 0)), 2) AS payment_total
FROM olist_orders AS o
LEFT JOIN payment_by_order AS p ON p.order_id = o.order_id
GROUP BY SUBSTR(o.order_purchase_timestamp, 1, 7)
ORDER BY month
""",
    ),
    GoldQuery(
        "top_categories",
        """
SELECT
    COALESCE(
        t.product_category_name_english,
        p.product_category_name,
        'uncategorized'
    ) AS category,
    COUNT(DISTINCT i.order_id) AS order_count,
    ROUND(SUM(i.price), 2) AS item_revenue
FROM olist_order_items AS i
JOIN olist_products AS p ON p.product_id = i.product_id
LEFT JOIN olist_category_translation AS t
    ON t.product_category_name = p.product_category_name
GROUP BY COALESCE(
    t.product_category_name_english,
    p.product_category_name,
    'uncategorized'
)
ORDER BY item_revenue DESC, category
LIMIT 10
""",
    ),
    GoldQuery(
        "top_customer_states",
        PAYMENT_BY_ORDER
        + """
SELECT
    c.customer_state AS state,
    COUNT(*) AS order_count,
    ROUND(SUM(COALESCE(p.payment_total, 0)), 2) AS payment_total
FROM olist_orders AS o
JOIN olist_customers AS c ON c.customer_id = o.customer_id
LEFT JOIN payment_by_order AS p ON p.order_id = o.order_id
GROUP BY c.customer_state
ORDER BY payment_total DESC, state
LIMIT 10
""",
    ),
    GoldQuery(
        "delivery_quality",
        """
SELECT
    COUNT(*) AS delivered_orders,
    ROUND(AVG(
        JULIANDAY(order_delivered_customer_date)
        - JULIANDAY(order_purchase_timestamp)
    ), 4) AS avg_delivery_days,
    SUM(CASE
        WHEN order_delivered_customer_date > order_estimated_delivery_date
        THEN 1 ELSE 0
    END) AS late_orders,
    ROUND(100.0 * SUM(CASE
        WHEN order_delivered_customer_date > order_estimated_delivery_date
        THEN 1 ELSE 0
    END) / COUNT(*), 4) AS late_rate_pct
FROM olist_orders
WHERE order_delivered_customer_date IS NOT NULL
""",
        mysql_sql="""
SELECT
    COUNT(*) AS delivered_orders,
    ROUND(AVG(
        TIMESTAMPDIFF(
            SECOND,
            order_purchase_timestamp,
            order_delivered_customer_date
        ) / 86400.0
    ), 4) AS avg_delivery_days,
    SUM(CASE
        WHEN order_delivered_customer_date > order_estimated_delivery_date
        THEN 1 ELSE 0
    END) AS late_orders,
    ROUND(100.0 * SUM(CASE
        WHEN order_delivered_customer_date > order_estimated_delivery_date
        THEN 1 ELSE 0
    END) / COUNT(*), 4) AS late_rate_pct
FROM olist_orders
WHERE order_delivered_customer_date IS NOT NULL
""",
    ),
    GoldQuery(
        "review_delivery",
        """
SELECT
    r.review_score,
    COUNT(*) AS reviewed_deliveries,
    ROUND(AVG(
        JULIANDAY(o.order_delivered_customer_date)
        - JULIANDAY(o.order_purchase_timestamp)
    ), 4) AS avg_delivery_days,
    ROUND(100.0 * SUM(CASE
        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
        THEN 1 ELSE 0
    END) / COUNT(*), 4) AS late_rate_pct
FROM olist_order_reviews AS r
JOIN olist_orders AS o ON o.order_id = r.order_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY r.review_score
ORDER BY r.review_score
""",
        mysql_sql="""
SELECT
    r.review_score,
    COUNT(*) AS reviewed_deliveries,
    ROUND(AVG(
        TIMESTAMPDIFF(
            SECOND,
            o.order_purchase_timestamp,
            o.order_delivered_customer_date
        ) / 86400.0
    ), 4) AS avg_delivery_days,
    ROUND(100.0 * SUM(CASE
        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
        THEN 1 ELSE 0
    END) / COUNT(*), 4) AS late_rate_pct
FROM olist_order_reviews AS r
JOIN olist_orders AS o ON o.order_id = r.order_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY r.review_score
ORDER BY r.review_score
""",
    ),
    GoldQuery(
        "payment_methods",
        """
SELECT
    payment_type,
    COUNT(DISTINCT order_id) AS order_count,
    ROUND(SUM(payment_value), 2) AS payment_total
FROM olist_order_payments
GROUP BY payment_type
ORDER BY payment_total DESC, payment_type
""",
    ),
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def execute_gold_queries(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    """Execute the complete read-only query suite on a supported engine."""

    answers: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as connection:
        for query in GOLD_QUERIES:
            result = connection.execute(text(query.for_dialect(engine.dialect.name)))
            answers[query.name] = [
                {name: _json_value(value) for name, value in row._mapping.items()}
                for row in result
            ]
    return answers
