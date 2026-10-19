"""Deterministic small-series selection for newly generated plans/drafts only."""

from typing import Any, Dict, Optional

from .schemas import (
    ChartEncoding,
    DashboardPlan,
    DashboardSchemaV1,
    DashboardVisualization,
    DashboardWidget,
    WidgetQueryResult,
    WidgetType,
)

MAX_SMALL_SERIES_POINTS = 3
PLAN_POINT_GUIDANCE = (
    "When exploration establishes cardinality, set expected_data_points to the "
    "number of distinct X categories, not the rows across series. Unknown is null, "
    "not zero. The server converts line/area charts with at most "
    f"{MAX_SMALL_SERIES_POINTS} points to bars; a single scalar becomes a KPI."
)


def _reason(count: int, target: str, basis: str) -> str:
    return (
        f"[small-series] {basis}：{count} 个数据点，"
        f"不超过 {MAX_SMALL_SERIES_POINTS}；改用 {target}，避免误示连续趋势。"
    )


def _note(previous: str, message: str, limit: int) -> str:
    if message in previous:
        return previous
    return (previous[: max(0, limit - len(message) - 1)] + "\n" + message).strip()


def normalize_plan_chart_selection(
    plan: DashboardPlan, temporal_evidence: Optional[Dict[str, Any]] = None
) -> DashboardPlan:
    """Do not guess unknown cardinality or mutate the caller's saved plan."""
    normalized = plan.model_copy(deep=True)
    for widget in normalized.widgets:
        # Exact source-column matches only: no dataset names or fuzzy date rules.
        if temporal_evidence and len(widget.dimensions) == 1:
            dimension = widget.dimensions[0].casefold()
            matches = [
                fact
                for fact in temporal_evidence.get("columns", [])
                if dimension
                in {
                    str(fact.get("column", "")).casefold(),
                    f"{fact.get('table')}.{fact.get('column')}".casefold(),
                }
                and fact.get("status") == "observed"
                and fact.get("distinct_domain_complete") is True
            ]
            if len(matches) == 1:
                observed = matches[0].get("source_distinct_count")
                # A small raw domain proves an upper bound; a large date domain
                # does not establish the count after month/year aggregation.
                if (
                    isinstance(observed, int)
                    and 0 < observed <= MAX_SMALL_SERIES_POINTS
                ):
                    widget.expected_data_points = observed
        count = widget.expected_data_points
        if (
            widget.type != WidgetType.LINE
            or count is None
            or not 0 < count <= MAX_SMALL_SERIES_POINTS
        ):
            continue
        target = (
            WidgetType.KPI if count == 1 and not widget.dimensions else WidgetType.BAR
        )
        widget.type = target
        widget.rationale = _note(
            widget.rationale, _reason(count, target.value, "规划探索数量"), 1000
        )
    return normalized


def normalize_executed_chart(
    schema: DashboardSchemaV1, widget: DashboardWidget, result: WidgetQueryResult
) -> bool:
    """Only the new generation buffer is changed, never refresh/read snapshots.

    Count actual distinct X values (long-form three-series data is not nine
    time points). Unknown, errored, empty or truncated results prove nothing.
    """
    visual = widget.presentation.visualization
    if visual not in (
        DashboardVisualization.LINE,
        DashboardVisualization.AREA,
    ) and not (visual is None and widget.type == WidgetType.LINE):
        return False
    if result.error or result.truncated or not result.rows:
        return False
    x, y = widget.encoding.x, widget.encoding.y
    if x not in result.columns or y not in result.columns:
        return False
    x_index, y_index = result.columns.index(x), result.columns.index(y)
    if any(row[x_index] is None for row in result.rows):
        return False
    count = len({str(row[x_index]) for row in result.rows})
    if count > MAX_SMALL_SERIES_POINTS:
        return False
    scalar = len(result.rows) == 1 and isinstance(result.rows[0][y_index], (int, float))
    target = WidgetType.KPI if scalar else WidgetType.BAR
    widget.type = target
    widget.presentation.visualization = (
        DashboardVisualization.KPI if scalar else DashboardVisualization.COLUMN
    )
    if scalar:
        widget.encoding = ChartEncoding(value=y)
    message = _reason(count, target.value, "真实试运行类别数")
    widget.description = _note(widget.description or "", message, 2000)
    compatibility = schema.metadata.compatibility
    plans = [
        compatibility.get("dashboard_plan"),
        (compatibility.get("agent_dashboard_workflow") or {}).get("plan"),
    ]
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        for item in plan.get("widgets", []):
            if item.get("id") == widget.id:
                item["type"] = target.value
                item["expected_data_points"] = count
                item["rationale"] = _note(item.get("rationale", ""), message, 1000)
    return True
