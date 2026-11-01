from datetime import datetime

import pytest

from dbgpt_app.openapi.api_v1.dashboard.anomaly_detection import (
    attach_widget_anomalies,
    evaluate_anomaly_rule,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAnomalyRule,
    DashboardAnomalyStatus,
    DashboardSchemaV1,
    DashboardWidget,
    WidgetError,
    WidgetQueryResult,
    collect_schema_issues,
    model_dump_compat,
)


def _rule(**overrides) -> DashboardAnomalyRule:
    payload = {
        "id": "revenue-change",
        "label": "Revenue change",
        "baseline": "previous_period",
        "value_field": "revenue",
        "time_field": "period",
        "direction": "two_sided",
        "threshold": {"mode": "relative_change", "value": 0.2},
        "rolling_window": 3,
        "min_samples": 1,
        "enabled": True,
    }
    payload.update(overrides)
    return DashboardAnomalyRule.model_validate(payload)


def _widget(rule: DashboardAnomalyRule) -> DashboardWidget:
    return DashboardWidget.model_validate(
        {
            "id": "revenue-widget",
            "type": "line",
            "title": "Revenue",
            "query": {
                "data_source_id": "demo",
                "sql": "SELECT period, revenue FROM revenue",
                "output_fields": [
                    {"name": "period", "type": "date"},
                    {"name": "revenue", "type": "number"},
                ],
            },
            "encoding": {"x": "period", "y": "revenue"},
            "anomaly_rules": [rule.model_dump(mode="json")],
        }
    )


def test_previous_period_anomaly_contains_complete_deterministic_evidence():
    evidence = evaluate_anomaly_rule(
        _rule(),
        ["period", "revenue"],
        [["2026-07", 80], ["2026-08", 100]],
    )

    assert evidence.status == DashboardAnomalyStatus.ANOMALY
    assert evidence.current_value == 100
    assert evidence.baseline_value == 80
    assert evidence.absolute_change == 20
    assert evidence.change_ratio == 0.25
    assert evidence.threshold.value == 0.2
    assert evidence.comparison_time_range.current_start == "2026-08"
    assert evidence.comparison_time_range.baseline_start == "2026-07"
    assert evidence.sample_size == 2
    assert evidence.matched_rule == "abs(change_ratio) >= 0.2"
    assert evidence.reason_code is None


def test_v95_time_field_orders_observations_and_rejects_duplicate_dates():
    evidence = evaluate_anomaly_rule(
        _rule(), ["period", "revenue"], [["2026-09-07", 70], ["2026-09-06", 100]]
    )
    assert evidence.status == DashboardAnomalyStatus.ANOMALY
    assert evidence.current_value == 70 and evidence.baseline_value == 100
    duplicate = evaluate_anomaly_rule(
        _rule(), ["period", "revenue"], [["2026-09-07", 70], ["2026-09-07", 100]]
    )
    assert duplicate.status == DashboardAnomalyStatus.INDETERMINATE
    assert duplicate.reason_code == "invalid_time_series"


def test_rolling_average_and_business_target_baselines_are_supported():
    rolling = evaluate_anomaly_rule(
        _rule(baseline="rolling_average", rolling_window=3),
        ["period", "revenue"],
        [["w1", 100], ["w2", 100], ["w3", 100], ["w4", 130]],
    )
    target = evaluate_anomaly_rule(
        _rule(
            baseline="target_value",
            target_value=100,
            direction="below",
            threshold={"mode": "relative_change", "value": 0.05},
        ),
        ["period", "revenue"],
        [["2026-08", 90]],
    )

    assert rolling.status == DashboardAnomalyStatus.ANOMALY
    assert rolling.baseline_value == 100
    assert rolling.change_ratio == 0.3
    assert rolling.comparison_time_range.baseline_start == "w1"
    assert rolling.comparison_time_range.baseline_end == "w3"
    assert target.status == DashboardAnomalyStatus.ANOMALY
    assert target.baseline_value == 100
    assert target.change_ratio == -0.1
    assert target.comparison_time_range.baseline_start == "business_target"


def test_threshold_is_configuration_not_a_hard_coded_percentage():
    rows = [["2026-07", 100], ["2026-08", 125]]
    lower = evaluate_anomaly_rule(
        _rule(threshold={"mode": "relative_change", "value": 0.2}),
        ["period", "revenue"],
        rows,
    )
    higher = evaluate_anomaly_rule(
        _rule(threshold={"mode": "relative_change", "value": 0.3}),
        ["period", "revenue"],
        rows,
    )

    assert lower.status == DashboardAnomalyStatus.ANOMALY
    assert higher.status == DashboardAnomalyStatus.NORMAL


@pytest.mark.parametrize(
    ("rule", "rows", "reason_code"),
    [
        (_rule(), [], "no_data"),
        (_rule(), [["2026-08", None]], "current_value_missing"),
        (_rule(), [["2026-08", 100]], "insufficient_data"),
        (
            _rule(baseline="rolling_average", rolling_window=3),
            [["w1", 100], ["w2", None], ["w3", 100], ["w4", 130]],
            "insufficient_data",
        ),
        (
            _rule(baseline="target_value", target_value=None),
            [["2026-08", 100]],
            "target_value_missing",
        ),
        (
            _rule(threshold={"mode": "relative_change", "value": 0.1}),
            [["2026-07", 0], ["2026-08", 10]],
            "zero_denominator",
        ),
        (
            _rule(threshold={"mode": "relative_change", "value": None}),
            [["2026-07", 100], ["2026-08", 120]],
            "threshold_missing",
        ),
    ],
)
def test_missing_insufficient_and_zero_denominator_are_indeterminate(
    rule, rows, reason_code
):
    evidence = evaluate_anomaly_rule(rule, ["period", "revenue"], rows)

    assert evidence.status == DashboardAnomalyStatus.INDETERMINATE
    assert evidence.reason_code == reason_code


def test_absolute_threshold_can_evaluate_a_zero_baseline_without_division():
    evidence = evaluate_anomaly_rule(
        _rule(threshold={"mode": "absolute_change", "value": 5}),
        ["period", "revenue"],
        [["2026-07", 0], ["2026-08", 10]],
    )

    assert evidence.status == DashboardAnomalyStatus.ANOMALY
    assert evidence.absolute_change == 10
    assert evidence.change_ratio is None


def test_query_failure_is_saved_as_indeterminate_evidence():
    result = WidgetQueryResult(
        widget_id="revenue-widget",
        refreshed_at=datetime.now(),
        error=WidgetError(code="query_failed", message="offline", retryable=True),
    )

    attached = attach_widget_anomalies(_widget(_rule()), result)

    assert attached.anomalies[0].status == DashboardAnomalyStatus.INDETERMINATE
    assert attached.anomalies[0].reason_code == "query_error"


def test_evidence_is_serialized_with_widget_results_for_snapshot_persistence():
    result = WidgetQueryResult(
        widget_id="revenue-widget",
        columns=["period", "revenue"],
        rows=[["2026-07", 100], ["2026-08", 130]],
        row_count=2,
        refreshed_at=datetime.now(),
    )

    serialized = model_dump_compat(attach_widget_anomalies(_widget(_rule()), result))

    assert serialized["anomalies"][0]["status"] == "anomaly"
    assert serialized["anomalies"][0]["current_value"] == 130
    assert serialized["anomalies"][0]["comparison_time_range"] == {
        "current_start": "2026-08",
        "current_end": "2026-08",
        "baseline_start": "2026-07",
        "baseline_end": "2026-07",
    }


def test_enabled_rules_require_declared_fields_thresholds_and_targets():
    widget = _widget(
        _rule(
            baseline="target_value",
            value_field="missing_metric",
            time_field="missing_time",
            target_value=None,
            threshold={"mode": "relative_change", "value": None},
        )
    )
    schema = DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.3",
            "dashboard": {"title": "Anomalies", "data_source_id": "demo"},
            "widgets": [widget.model_dump(mode="json")],
            "layouts": {
                "desktop": [
                    {
                        "widget_id": "revenue-widget",
                        "x": 0,
                        "y": 0,
                        "w": 6,
                        "h": 4,
                    }
                ]
            },
        }
    )

    assert {issue.code for issue in collect_schema_issues(schema)} >= {
        "unknown_anomaly_value_field",
        "unknown_anomaly_time_field",
        "anomaly_threshold_required",
        "anomaly_target_required",
    }
