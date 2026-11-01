"""Deterministic anomaly evaluation for dashboard widget results.

The detector deliberately has no model dependency.  It evaluates owner-configured
rules against query results and returns complete evidence that can be serialized in
live and immutable published snapshots.  AI may explain this evidence, but it is not
part of the decision path.
"""

from __future__ import annotations

import math
import re
from statistics import fmean
from typing import Any, Dict, List, Optional, Sequence

from .schemas import (
    DashboardAnomalyBaseline,
    DashboardAnomalyComparisonRange,
    DashboardAnomalyDirection,
    DashboardAnomalyEvidence,
    DashboardAnomalyRule,
    DashboardAnomalyStatus,
    DashboardAnomalyThresholdMode,
    DashboardWidget,
    WidgetQueryResult,
)


def _finite_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _column_index(columns: Sequence[str], field: Optional[str]) -> Optional[int]:
    if not field:
        return None
    if field in columns:
        return columns.index(field)
    matches = [
        index
        for index, name in enumerate(columns)
        if name.casefold() == field.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _row_value(rows: Sequence[Sequence[Any]], row_index: int, column_index: int) -> Any:
    row = rows[row_index]
    return row[column_index] if column_index < len(row) else None


def _range_marker(
    rows: Sequence[Sequence[Any]], row_index: int, time_index: Optional[int]
) -> str:
    if time_index is not None:
        raw = _row_value(rows, row_index, time_index)
        if raw is not None:
            return str(raw)
    return f"row:{row_index + 1}"


def _comparison_range(
    rows: Sequence[Sequence[Any]],
    current_index: Optional[int],
    baseline_indices: Sequence[int],
    time_index: Optional[int],
    *,
    target: bool = False,
) -> DashboardAnomalyComparisonRange:
    current = (
        _range_marker(rows, current_index, time_index)
        if current_index is not None
        else None
    )
    if target:
        baseline_start = baseline_end = "business_target"
    elif baseline_indices:
        baseline_start = _range_marker(rows, baseline_indices[0], time_index)
        baseline_end = _range_marker(rows, baseline_indices[-1], time_index)
    else:
        baseline_start = baseline_end = None
    return DashboardAnomalyComparisonRange(
        current_start=current,
        current_end=current,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
    )


def _rule_expression(rule: DashboardAnomalyRule) -> str:
    value = rule.threshold.value
    metric = (
        "change_ratio"
        if rule.threshold.mode == DashboardAnomalyThresholdMode.RELATIVE_CHANGE
        else "absolute_change"
    )
    if value is None:
        return f"{metric}: threshold_not_configured"
    if rule.direction == DashboardAnomalyDirection.TWO_SIDED:
        return f"abs({metric}) >= {value:g}"
    if rule.direction == DashboardAnomalyDirection.ABOVE:
        return f"{metric} >= {value:g}"
    return f"{metric} <= {-value:g}"


def _indeterminate(
    rule: DashboardAnomalyRule,
    *,
    reason_code: str,
    reason: str,
    sample_size: int = 0,
    current_value: Optional[float] = None,
    baseline_value: Optional[float] = None,
    absolute_change: Optional[float] = None,
    change_ratio: Optional[float] = None,
    comparison_time_range: Optional[DashboardAnomalyComparisonRange] = None,
) -> DashboardAnomalyEvidence:
    return DashboardAnomalyEvidence(
        rule_id=rule.id,
        rule_label=rule.label,
        status=DashboardAnomalyStatus.INDETERMINATE,
        baseline=rule.baseline,
        current_value=current_value,
        baseline_value=baseline_value,
        absolute_change=absolute_change,
        change_ratio=change_ratio,
        threshold=rule.threshold,
        comparison_time_range=(
            comparison_time_range or DashboardAnomalyComparisonRange()
        ),
        sample_size=sample_size,
        matched_rule=_rule_expression(rule),
        reason_code=reason_code,
        reason=reason,
    )


def evaluate_anomaly_rule(
    rule: DashboardAnomalyRule,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    query_error: Optional[str] = None,
) -> DashboardAnomalyEvidence:
    """Evaluate one rule using the final row as the current observation."""

    if query_error:
        return _indeterminate(
            rule,
            reason_code="query_error",
            reason=f"The widget query failed: {query_error}",
        )

    value_index = _column_index(columns, rule.value_field)
    if value_index is None:
        return _indeterminate(
            rule,
            reason_code="value_field_missing",
            reason=f"Value field '{rule.value_field}' is missing from the result.",
        )
    time_index = _column_index(columns, rule.time_field)
    if rule.time_field and time_index is None:
        return _indeterminate(
            rule,
            reason_code="time_field_missing",
            reason=f"Time field '{rule.time_field}' is missing from the result.",
        )
    if not rows:
        return _indeterminate(
            rule,
            reason_code="no_data",
            reason="The query returned no observations.",
        )

    if time_index is not None and any(
        re.match(
            r"^(?:\d{4}-|w\d+$)", str(_row_value(rows, i, time_index)), re.IGNORECASE
        )
        for i in range(len(rows))
    ):
        from datetime import datetime, timezone

        try:

            def time_key(row):
                raw = str(row[time_index]).strip()
                if re.fullmatch(r"w\d+", raw, re.IGNORECASE):
                    return float(raw[1:])
                if len(raw) == 7:
                    raw += "-01"
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return (
                    value.replace(tzinfo=timezone.utc).timestamp()
                    if value.tzinfo is None
                    else value.timestamp()
                )

            keys = [time_key(row) for row in rows]
            if len(set(keys)) != len(keys):
                raise ValueError("duplicate periods")
            rows = [row for _, row in sorted(zip(keys, rows), key=lambda pair: pair[0])]
        except (ValueError, TypeError, IndexError, OverflowError):
            return _indeterminate(
                rule,
                reason_code="invalid_time_series",
                reason="时间字段需要有效且不重复的日期；请先按周期汇总数据。",
            )

    numeric_values = [
        _finite_number(_row_value(rows, index, value_index))
        for index in range(len(rows))
    ]
    sample_size = sum(value is not None for value in numeric_values)
    current_index = len(rows) - 1
    current_value = numeric_values[current_index]
    if current_value is None:
        return _indeterminate(
            rule,
            reason_code="current_value_missing",
            reason="The current observation is missing or not numeric.",
            sample_size=sample_size,
            comparison_time_range=_comparison_range(
                rows, current_index, [], time_index
            ),
        )

    baseline_indices: List[int] = []
    baseline_value: Optional[float]
    target_baseline = rule.baseline == DashboardAnomalyBaseline.TARGET_VALUE
    required_samples = rule.min_samples
    if rule.baseline == DashboardAnomalyBaseline.PREVIOUS_PERIOD:
        required_samples = max(required_samples, 2)
        if len(rows) < 2:
            return _indeterminate(
                rule,
                reason_code="insufficient_data",
                reason="Previous-period comparison requires at least two observations.",
                sample_size=sample_size,
                current_value=current_value,
                comparison_time_range=_comparison_range(
                    rows, current_index, [], time_index
                ),
            )
        baseline_indices = [current_index - 1]
        baseline_value = numeric_values[current_index - 1]
    elif rule.baseline == DashboardAnomalyBaseline.ROLLING_AVERAGE:
        required_samples = max(required_samples, rule.rolling_window + 1)
        if len(rows) < rule.rolling_window + 1:
            return _indeterminate(
                rule,
                reason_code="insufficient_data",
                reason=(
                    "Rolling-average comparison requires the current observation and "
                    f"{rule.rolling_window} preceding observations."
                ),
                sample_size=sample_size,
                current_value=current_value,
                comparison_time_range=_comparison_range(
                    rows, current_index, [], time_index
                ),
            )
        baseline_indices = list(
            range(current_index - rule.rolling_window, current_index)
        )
        baseline_values = [numeric_values[index] for index in baseline_indices]
        baseline_value = (
            fmean(value for value in baseline_values if value is not None)
            if all(value is not None for value in baseline_values)
            else None
        )
    else:
        required_samples = max(required_samples, 1)
        baseline_value = _finite_number(rule.target_value)

    comparison = _comparison_range(
        rows,
        current_index,
        baseline_indices,
        time_index,
        target=target_baseline,
    )
    if sample_size < required_samples:
        return _indeterminate(
            rule,
            reason_code="insufficient_data",
            reason=(
                f"Only {sample_size} numeric observations are available; "
                f"{required_samples} are required."
            ),
            sample_size=sample_size,
            current_value=current_value,
            baseline_value=baseline_value,
            comparison_time_range=comparison,
        )
    if baseline_value is None:
        reason_code = (
            "target_value_missing" if target_baseline else "baseline_value_missing"
        )
        return _indeterminate(
            rule,
            reason_code=reason_code,
            reason="The configured baseline is missing or not numeric.",
            sample_size=sample_size,
            current_value=current_value,
            comparison_time_range=comparison,
        )

    absolute_change = current_value - baseline_value
    change_ratio = (
        absolute_change / abs(baseline_value) if baseline_value != 0 else None
    )
    if rule.threshold.value is None:
        return _indeterminate(
            rule,
            reason_code="threshold_missing",
            reason="No decision threshold is configured for this rule.",
            sample_size=sample_size,
            current_value=current_value,
            baseline_value=baseline_value,
            absolute_change=absolute_change,
            change_ratio=change_ratio,
            comparison_time_range=comparison,
        )
    if (
        rule.threshold.mode == DashboardAnomalyThresholdMode.RELATIVE_CHANGE
        and baseline_value == 0
    ):
        return _indeterminate(
            rule,
            reason_code="zero_denominator",
            reason="Relative change cannot be calculated because the baseline is zero.",
            sample_size=sample_size,
            current_value=current_value,
            baseline_value=baseline_value,
            absolute_change=absolute_change,
            comparison_time_range=comparison,
        )

    metric = (
        change_ratio
        if rule.threshold.mode == DashboardAnomalyThresholdMode.RELATIVE_CHANGE
        else absolute_change
    )
    assert metric is not None
    threshold = rule.threshold.value
    if rule.direction == DashboardAnomalyDirection.TWO_SIDED:
        anomaly = abs(metric) >= threshold
    elif rule.direction == DashboardAnomalyDirection.ABOVE:
        anomaly = metric >= threshold
    else:
        anomaly = metric <= -threshold

    return DashboardAnomalyEvidence(
        rule_id=rule.id,
        rule_label=rule.label,
        status=(
            DashboardAnomalyStatus.ANOMALY if anomaly else DashboardAnomalyStatus.NORMAL
        ),
        baseline=rule.baseline,
        current_value=current_value,
        baseline_value=baseline_value,
        absolute_change=absolute_change,
        change_ratio=change_ratio,
        threshold=rule.threshold,
        comparison_time_range=comparison,
        sample_size=sample_size,
        matched_rule=_rule_expression(rule),
    )


def evaluate_widget_anomalies(
    widget: DashboardWidget, result: WidgetQueryResult
) -> List[DashboardAnomalyEvidence]:
    """Evaluate all enabled rules and fail safely per rule."""

    evidence: List[DashboardAnomalyEvidence] = []
    query_error = result.error.message if result.error else None
    for rule in widget.anomaly_rules:
        if not rule.enabled:
            continue
        try:
            evidence.append(
                evaluate_anomaly_rule(
                    rule,
                    result.columns,
                    result.rows,
                    query_error=query_error,
                )
            )
        except Exception as exc:  # defensive: a detector error must never misreport
            evidence.append(
                _indeterminate(
                    rule,
                    reason_code="detector_error",
                    reason=(
                        f"The deterministic detector could not evaluate the rule: {exc}"
                    ),
                )
            )
    return evidence


def attach_widget_anomalies(
    widget: DashboardWidget, result: WidgetQueryResult
) -> WidgetQueryResult:
    """Attach serializable evidence to a mutable Pydantic result model."""

    result.anomalies = evaluate_widget_anomalies(widget, result)
    return result


def anomaly_evidence_by_widget(
    widgets: Sequence[DashboardWidget],
    results: Dict[str, WidgetQueryResult],
) -> Dict[str, List[DashboardAnomalyEvidence]]:
    """Small helper used by callers that synthesize result dictionaries."""

    widget_by_id = {widget.id: widget for widget in widgets}
    return {
        widget_id: evaluate_widget_anomalies(widget_by_id[widget_id], result)
        for widget_id, result in results.items()
        if widget_id in widget_by_id
    }
