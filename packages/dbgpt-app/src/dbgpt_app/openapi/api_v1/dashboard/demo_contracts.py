"""Verified deterministic contracts for local dashboard demo data sources.

These contracts are deliberately narrow.  They are not a general SQL generator and
they never weaken normal schema or publication validation.  Their purpose is to make
the checked-in Olist acceptance data reproducible when a model omits or malformed the
share-page publication part of an otherwise confirmed dashboard plan.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .schemas import (
    DashboardPlan,
    DashboardQueryDraftRequest,
    DashboardSchemaV1,
    DashboardWidgetQueryDraft,
    model_dump_compat,
    model_validate_compat,
)

OLIST_DEMO_SOURCE_ID = "olist_ecommerce_demo"


def _olist_schema_path() -> Optional[Path]:
    current = Path(__file__).resolve()
    for root in current.parents:
        candidate = (
            root
            / "examples"
            / "dashboard"
            / "schemas"
            / ("olist-ecommerce.schema.json")
        )
        if candidate.is_file():
            return candidate
    return None


def _fold(*values: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", " ".join(values).casefold())


def _filter_role(item) -> Optional[str]:
    text = _fold(item.id, item.label, item.field)
    if any(token in text for token in ("财年", "购买年", "purchaseyear", "fiscalyear")):
        return "purchase-years"
    if any(token in text for token in ("客户州", "州", "customerstate")):
        return "customer-states"
    if any(token in text for token in ("订单状态", "orderstatus")):
        return "order-status"
    return None


def _widget_role(item) -> Optional[str]:
    text = _fold(
        item.id,
        item.title,
        item.business_question,
        item.metric,
        *item.dimensions,
    )
    if any(
        token in text
        for token in ("订单明细", "订单核对", "核对表", "orderdetail", "details")
    ):
        return "order-detail"
    if any(token in text for token in ("评分分布", "评价分布", "reviewdistribution")):
        return "review-distribution"
    if any(token in text for token in ("品类成交额", "品类收入", "categoryrevenue")):
        return "category-revenue"
    if any(token in text for token in ("月度", "monthly")) and any(
        token in text for token in ("支付", "payment", "趋势", "trend")
    ):
        return "monthly-payments"
    if any(token in text for token in ("已送达率", "送达率", "deliveredrate")):
        return "delivered-rate"
    if any(token in text for token in ("支付总额", "totalpayment", "paymenttotal")):
        return "payment-total"
    return None


def _load_olist_schema() -> Optional[DashboardSchemaV1]:
    path = _olist_schema_path()
    if path is None:
        return None
    return model_validate_compat(
        DashboardSchemaV1, json.loads(path.read_text(encoding="utf-8"))
    )


def verified_olist_plan_for_request(
    user_prompt: str, data_source_id: str
) -> Optional[DashboardPlan]:
    """Return the verified 6x3 plan for an explicit standard Olist request."""

    if data_source_id != OLIST_DEMO_SOURCE_ID:
        return None
    prompt = _fold(user_prompt)
    required_intent_groups = (
        ("购买年份", "purchaseyear"),
        ("客户州", "customerstate"),
        ("订单状态", "orderstatus"),
        ("支付总额", "paymenttotal", "totalpayment"),
        ("已送达率", "送达率", "deliveredrate"),
        ("月度", "monthly"),
        ("品类", "category"),
        ("评分分布", "评价分布", "reviewdistribution"),
        ("订单明细", "订单核对", "核对表", "orderdetail"),
    )
    if not all(
        any(intent in prompt for intent in alternatives)
        for alternatives in required_intent_groups
    ):
        return None
    template = _load_olist_schema()
    if template is None:
        return None

    filters = []
    for item in template.filters:
        payload = model_dump_compat(item)
        if item.id == "purchase-years":
            payload["field"] = "order_purchase_timestamp"
        filters.append(payload)

    metrics_by_widget = {
        "payment-total": "支付总额",
        "delivered-rate": "已送达率",
        "monthly-payments": "支付总额",
        "category-revenue": "商品成交额",
        "review-distribution": "评价数",
        "order-detail": "支付总额",
    }
    dimensions_by_widget = {
        "payment-total": [],
        "delivered-rate": [],
        "monthly-payments": ["购买月份"],
        "category-revenue": ["商品英文品类"],
        "review-distribution": ["评分"],
        "order-detail": ["购买年份", "客户州", "订单状态"],
    }
    widgets = [
        {
            "id": item.id,
            "type": item.type.value,
            "title": item.title,
            "business_question": item.description or item.title,
            "metric": metrics_by_widget[item.id],
            "dimensions": dimensions_by_widget[item.id],
        }
        for item in template.widgets
    ]
    return model_validate_compat(
        DashboardPlan,
        {
            "title": "Olist 电商经营与履约看板",
            "description": template.dashboard.description,
            "business_theme": "Olist 电商经营、客户体验与订单履约分析",
            "metrics": ["支付总额", "已送达率", "商品成交额", "评价数"],
            "dimensions": [
                "购买月份",
                "购买年份",
                "客户州",
                "订单状态",
                "商品英文品类",
                "评分",
            ],
            "filters": filters,
            "widgets": widgets,
        },
    )


def normalize_verified_olist_plan(
    plan: DashboardPlan, user_prompt: str, data_source_id: str
) -> Tuple[DashboardPlan, bool]:
    """Constrain an explicit standard Olist request to the verified 6x3 plan."""

    normalized = verified_olist_plan_for_request(user_prompt, data_source_id)
    return (normalized, True) if normalized is not None else (plan, False)


def repair_verified_olist_generation_contract(
    plan: DashboardPlan,
    query_request: DashboardQueryDraftRequest,
    data_source_id: str,
) -> Tuple[DashboardPlan, DashboardQueryDraftRequest, List[str]]:
    """Replace matching Olist query drafts with the checked-in verified contract.

    The fallback activates only for the uniquely named local Olist source, only when
    all three canonical filters are present, and only for semantically recognised
    widgets.  Unknown or extra widgets are left untouched so normal validation can
    reject an incomplete repair with exact component IDs.
    """

    if data_source_id != OLIST_DEMO_SOURCE_ID:
        return plan, query_request, []
    template = _load_olist_schema()
    if template is None:
        return plan, query_request, []

    plan_filter_by_role = {
        role: item for item in plan.filters if (role := _filter_role(item)) is not None
    }
    required_filter_roles = {"purchase-years", "customer-states", "order-status"}
    if set(plan_filter_by_role) != required_filter_roles or len(plan.filters) != 3:
        return plan, query_request, []

    template_filters = {item.id: item for item in template.filters}
    filter_id_map = {
        role: plan_filter_by_role[role].id for role in required_filter_roles
    }
    normalized_filters = []
    for plan_filter in plan.filters:
        role = _filter_role(plan_filter)
        canonical = template_filters[role]
        normalized_filters.append(
            canonical.model_copy(
                update={"id": plan_filter.id, "label": plan_filter.label}
            )
            if hasattr(canonical, "model_copy")
            else canonical.copy(
                update={"id": plan_filter.id, "label": plan_filter.label}
            )
        )

    template_widgets = {item.id: item for item in template.widgets}
    submitted = {item.widget_id: item for item in query_request.widgets}
    repaired: List[str] = []
    repaired_queries: List[DashboardWidgetQueryDraft] = []
    for plan_widget in plan.widgets:
        role = _widget_role(plan_widget)
        canonical = template_widgets.get(role or "")
        if canonical is None or canonical.publication is None:
            if plan_widget.id in submitted:
                repaired_queries.append(submitted[plan_widget.id])
            continue

        publication = canonical.publication
        query_payload = {
            "widget_id": plan_widget.id,
            "sql": canonical.query.sql,
            "filter_parameters": {
                filter_id_map[filter_id]: binding
                for filter_id, binding in canonical.query.filter_parameters.items()
            },
            "default_parameters": canonical.query.default_parameters,
            "output_fields": [
                model_dump_compat(item) for item in canonical.query.output_fields
            ],
            "encoding": model_dump_compat(canonical.encoding),
            "timeout_seconds": canonical.query.timeout_seconds,
            "max_rows": canonical.query.max_rows,
            "grain": canonical.query.grain,
            "publication": {
                "query": {
                    "sql": publication.query.sql,
                    "default_parameters": publication.query.default_parameters,
                    "output_fields": [
                        model_dump_compat(item)
                        for item in publication.query.output_fields
                    ],
                    "timeout_seconds": publication.query.timeout_seconds,
                    "max_rows": publication.query.max_rows,
                },
                "filter_fields": {
                    filter_id_map[filter_id]: model_dump_compat(binding)
                    if not isinstance(binding, str)
                    else binding
                    for filter_id, binding in publication.filter_fields.items()
                },
                "group_by": publication.group_by,
                "measures": [model_dump_compat(item) for item in publication.measures],
                "output_columns": publication.output_columns,
                "row_mode": publication.row_mode,
                "sort": [model_dump_compat(item) for item in publication.sort],
                "max_output_rows": publication.max_output_rows,
            },
        }
        repaired_queries.append(
            model_validate_compat(DashboardWidgetQueryDraft, query_payload)
        )
        repaired.append(plan_widget.id)

    if not repaired:
        return plan, query_request, []
    effective_plan = (
        plan.model_copy(update={"filters": normalized_filters})
        if hasattr(plan, "model_copy")
        else plan.copy(update={"filters": normalized_filters})
    )
    effective_request = (
        query_request.model_copy(update={"widgets": repaired_queries})
        if hasattr(query_request, "model_copy")
        else query_request.copy(update={"widgets": repaired_queries})
    )
    return effective_plan, effective_request, repaired


def repair_safe_static_publication_contracts(
    query_request: DashboardQueryDraftRequest,
) -> Tuple[DashboardQueryDraftRequest, List[str]]:
    """Freeze parameter-free widgets without asking the model for boilerplate.

    A query that has no dashboard filter mapping can safely be materialized as-is
    and replayed in row mode.  Parameterized widgets are intentionally not rewritten:
    manufacturing their raw aggregation grain would risk incorrect public metrics.
    Those widgets continue through the strict validator and are reported precisely.
    """

    repaired: List[str] = []
    widgets: List[DashboardWidgetQueryDraft] = []
    for widget in query_request.widgets:
        if widget.publication is not None or widget.filter_parameters:
            widgets.append(widget)
            continue
        payload = model_dump_compat(widget)
        payload["publication"] = {
            "query": {
                "sql": widget.sql,
                "default_parameters": widget.default_parameters,
                "output_fields": [
                    model_dump_compat(item) for item in widget.output_fields
                ],
                "timeout_seconds": widget.timeout_seconds,
                "max_rows": widget.max_rows,
            },
            "filter_fields": {},
            "group_by": [],
            "measures": [],
            "output_columns": [item.name for item in widget.output_fields],
            "row_mode": True,
            "sort": [],
            "max_output_rows": widget.max_rows,
        }
        widgets.append(model_validate_compat(DashboardWidgetQueryDraft, payload))
        repaired.append(widget.widget_id)
    if not repaired:
        return query_request, []
    updated = (
        query_request.model_copy(update={"widgets": widgets})
        if hasattr(query_request, "model_copy")
        else query_request.copy(update={"widgets": widgets})
    )
    return updated, repaired
