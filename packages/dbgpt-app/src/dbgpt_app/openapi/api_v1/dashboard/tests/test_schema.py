import json
import re
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    SUPPORTED_SCHEMA_VERSIONS,
    DashboardAnnotationStatus,
    DashboardSchemaV1,
    DashboardSelectionKind,
    DashboardSortDirection,
    DashboardStatus,
    DashboardThemeDensity,
    DashboardThemeFontScale,
    DashboardThemeKpiStyle,
    DashboardThemeMode,
    DashboardThemePreset,
    DashboardThemeShadow,
    DashboardThemeTableStyle,
    DashboardVisualization,
    DataFieldType,
    FederationJoinType,
    FederationMode,
    FilterType,
    MetricAggregation,
    SemanticDefinitionSource,
    WidgetType,
    collect_schema_issues,
)


def valid_schema_dict():
    return {
        "schema_version": "1.0",
        "dashboard": {
            "id": "sales-dashboard",
            "title": "Sales overview",
            "data_source_id": "walmart",
        },
        "metric_context": {
            "grain": "one row per store and week",
            "data_freshness": "sample data",
            "source_notes": ["Walmart training sample"],
        },
        "filters": [
            {
                "id": "date",
                "type": "date_range",
                "label": "Date",
                "field": "date",
                "default": ["2010-01-01", "2012-12-31"],
            }
        ],
        "widgets": [
            {
                "id": "sales-trend",
                "type": "line",
                "title": "Sales trend",
                "query": {
                    "data_source_id": "walmart",
                    "sql": (
                        "SELECT date, SUM(weekly_sales) AS sales "
                        "FROM sales WHERE date BETWEEN :start_date AND :end_date "
                        "GROUP BY date"
                    ),
                    "filter_parameters": {
                        "date": {
                            "start_parameter": "start_date",
                            "end_parameter": "end_date",
                        }
                    },
                    "output_fields": [
                        {"name": "date", "type": "date"},
                        {"name": "sales", "type": "number"},
                    ],
                },
                "encoding": {"x": "date", "y": "sales"},
            }
        ],
        "layouts": {
            "desktop": [{"widget_id": "sales-trend", "x": 0, "y": 0, "w": 12, "h": 5}]
        },
    }


def test_valid_schema_has_no_cross_field_issues():
    schema = DashboardSchemaV1.model_validate(valid_schema_dict())
    assert collect_schema_issues(schema) == []


def test_publication_ratio_requires_a_denominator_field():
    payload = valid_schema_dict()
    payload["schema_version"] = "1.3"
    widget = payload["widgets"][0]
    widget["publication"] = {
        "query": {
            "data_source_id": "walmart",
            "sql": "SELECT date, sales, orders FROM sales",
            "output_fields": [
                {"name": "date", "type": "date"},
                {"name": "sales", "type": "number"},
                {"name": "orders", "type": "number"},
            ],
        },
        "filter_fields": {"date": "date"},
        "group_by": ["date"],
        "measures": [
            {
                "source_field": "sales",
                "output_field": "sales",
                "aggregation": "ratio",
            }
        ],
        "output_columns": ["date", "sales"],
    }
    schema = DashboardSchemaV1.model_validate(payload)

    assert "publication_ratio_denominator_required" in {
        issue.code for issue in collect_schema_issues(schema)
    }


def test_unknown_encoding_field_is_rejected():
    payload = valid_schema_dict()
    payload["widgets"][0]["encoding"]["y"] = "profit"
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "unknown_encoding_field" in {issue.code for issue in issues}


def test_duplicate_ids_and_layout_overflow_are_rejected():
    payload = valid_schema_dict()
    payload["filters"].append(dict(payload["filters"][0]))
    payload["layouts"]["desktop"][0].update({"x": 6, "w": 12})
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    codes = {issue.code for issue in issues}
    assert "duplicate_filter_id" in codes
    assert "layout_out_of_bounds" in codes


def test_sql_parameter_must_exist_in_widget_sql():
    payload = valid_schema_dict()
    payload["widgets"][0]["query"]["sql"] = (
        "SELECT date, weekly_sales AS sales FROM sales"
    )
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "missing_sql_parameter" in {issue.code for issue in issues}


def test_every_sql_parameter_requires_a_filter_mapping_or_component_default():
    payload = valid_schema_dict()
    payload["widgets"][0]["query"]["sql"] += " AND :fiscal_year IS NULL"

    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))

    unbound = [issue for issue in issues if issue.code == "unbound_sql_parameter"]
    assert len(unbound) == 1
    assert ":fiscal_year" in unbound[0].message

    payload["widgets"][0]["query"]["default_parameters"] = {"fiscal_year": "2024"}
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "unbound_sql_parameter" not in {issue.code for issue in issues}


def test_query_default_parameters_have_a_serialized_size_limit():
    payload = valid_schema_dict()
    payload["widgets"][0]["query"]["default_parameters"] = {
        "oversized": "x" * (64 * 1024)
    }
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "query_parameters_too_large" in {issue.code for issue in issues}


def test_schema_1_2_semantic_references_are_explicit_and_validated():
    payload = valid_schema_dict()
    payload["schema_version"] = "1.2"
    payload["metric_context"]["metrics"] = [
        {
            "id": "metric-sales",
            "name": "Sales",
            "business_definition": "Sum of weekly sales in the selected period.",
            "aggregation": "sum",
            "unit": "USD",
            "definition_source": "user_confirmed",
        }
    ]
    payload["metric_context"]["dimensions"] = [
        {
            "id": "dimension-date",
            "name": "Date",
            "business_definition": "Calendar date of the weekly observation.",
            "field": "date",
            "data_type": "date",
            "definition_source": "catalog",
        }
    ]
    payload["widgets"][0]["metric_ids"] = ["metric-sales"]
    payload["widgets"][0]["dimension_ids"] = ["dimension-date"]

    schema = DashboardSchemaV1.model_validate(payload)
    assert collect_schema_issues(schema) == []

    payload["widgets"][0]["metric_ids"] = ["metric-profit"]
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "unknown_metric_id" in {issue.code for issue in issues}


def test_schema_1_3_presentation_validates_visual_encoding_and_sort_field():
    payload = valid_schema_dict()
    payload["schema_version"] = "1.3"
    payload["widgets"][0]["encoding"].update(
        {"row": "date", "column": "store", "value": "sales"}
    )
    payload["widgets"][0]["query"]["output_fields"].append(
        {"name": "store", "type": "string"}
    )
    payload["widgets"][0]["presentation"] = {
        "visualization": "heatmap",
        "colors": ["#eff6ff", "#2563eb"],
        "default_sort": {"field": "sales", "direction": "descending"},
    }
    assert collect_schema_issues(DashboardSchemaV1.model_validate(payload)) == []

    payload["widgets"][0]["encoding"].pop("column")
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "missing_encoding" in {issue.code for issue in issues}

    payload["widgets"][0]["encoding"]["column"] = "store"
    payload["widgets"][0]["presentation"]["default_sort"]["field"] = "profit"
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "unknown_sort_field" in {issue.code for issue in issues}


def test_presentation_settings_require_schema_1_3_but_legacy_documents_still_work():
    payload = valid_schema_dict()
    legacy = DashboardSchemaV1.model_validate(payload)
    assert collect_schema_issues(legacy) == []

    payload["widgets"][0]["presentation"] = {"visualization": "area"}
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "presentation_requires_schema_1_3" in {issue.code for issue in issues}


def test_schema_1_4_requires_a_canonical_visual_theme_and_mode():
    payload = valid_schema_dict()
    payload["schema_version"] = "1.4"
    missing = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert {issue.code for issue in missing} >= {
        "canonical_theme_required",
        "theme_mode_required",
    }

    payload["dashboard"]["theme"] = {
        "preset": "clarity",
        "mode": "light",
        "overrides": {},
    }
    assert collect_schema_issues(DashboardSchemaV1.model_validate(payload)) == []


def test_legacy_theme_payloads_remain_readable_without_rewriting_them():
    payload = valid_schema_dict()
    payload["dashboard"]["theme"] = {
        "preset": "business_blue",
        "legacy_card_tone": "blue",
    }

    schema = DashboardSchemaV1.model_validate(payload)

    assert collect_schema_issues(schema) == []
    assert schema.dashboard.theme.preset.value == "business_blue"
    assert schema.dashboard.theme.model_extra == {"legacy_card_tone": "blue"}


@pytest.mark.parametrize("preset", ["clarity", "ocean", "warm", "graphite"])
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_every_builtin_visual_theme_passes_server_palette_checks(preset, mode):
    payload = valid_schema_dict()
    payload["schema_version"] = "1.4"
    payload["dashboard"]["theme"] = {
        "preset": preset,
        "mode": mode,
        "overrides": {},
    }

    assert collect_schema_issues(DashboardSchemaV1.model_validate(payload)) == []


def test_theme_overrides_require_schema_1_4_and_server_checks_palette_evidence():
    payload = valid_schema_dict()
    payload["dashboard"]["theme"] = {
        "preset": "clarity",
        "mode": "light",
        "overrides": {
            "primary_color": "#FDFDFD",
            "chart_palette": ["#FDFDFD", "#1D5FD1", "#1D5FD1"],
        },
    }
    legacy = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert "visual_theme_requires_schema_1_4" in {issue.code for issue in legacy}

    payload["schema_version"] = "1.4"
    issues = collect_schema_issues(DashboardSchemaV1.model_validate(payload))
    assert {issue.code for issue in issues} >= {
        "theme_primary_contrast_too_low",
        "theme_palette_contrast_too_low",
        "duplicate_theme_palette_color",
    }


def test_checked_in_json_schema_matches_pydantic_contract():
    schema_path = Path(__file__).parents[1] / "schema" / "dashboard.schema.json"
    assert (
        json.loads(schema_path.read_text(encoding="utf-8"))
        == DashboardSchemaV1.model_json_schema()
    )


def _repository_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "web" / "types" / "dashboard.ts").is_file():
            return candidate
    raise AssertionError("Could not locate the repository root from the schema tests.")


def _typescript_string_union(source: str, type_name: str) -> set[str]:
    match = re.search(rf"export type {re.escape(type_name)}\s*=\s*([^;]+);", source)
    assert match, f"Missing TypeScript union {type_name}."
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_typescript_dashboard_unions_match_python_contract():
    source = (_repository_root() / "web" / "types" / "dashboard.ts").read_text(
        encoding="utf-8"
    )
    expected = {
        "DashboardSchemaVersion": set(SUPPORTED_SCHEMA_VERSIONS),
        "DashboardStatus": {item.value for item in DashboardStatus},
        "DashboardWidgetType": {item.value for item in WidgetType},
        "DashboardFilterType": {item.value for item in FilterType},
        "DashboardFieldType": {item.value for item in DataFieldType},
        "DashboardFederationMode": {item.value for item in FederationMode},
        "DashboardFederationJoinType": {item.value for item in FederationJoinType},
        "DashboardMetricAggregation": {item.value for item in MetricAggregation},
        "DashboardSemanticDefinitionSource": {
            item.value for item in SemanticDefinitionSource
        },
        "DashboardVisualization": {item.value for item in DashboardVisualization},
        "DashboardSortDirection": {item.value for item in DashboardSortDirection},
        "DashboardSelectionKind": {item.value for item in DashboardSelectionKind},
        "DashboardThemePreset": {item.value for item in DashboardThemePreset},
        "DashboardThemeMode": {item.value for item in DashboardThemeMode},
        "DashboardThemeFontScale": {item.value for item in DashboardThemeFontScale},
        "DashboardThemeDensity": {item.value for item in DashboardThemeDensity},
        "DashboardThemeShadow": {item.value for item in DashboardThemeShadow},
        "DashboardThemeKpiStyle": {item.value for item in DashboardThemeKpiStyle},
        "DashboardThemeTableStyle": {item.value for item in DashboardThemeTableStyle},
        "DashboardAnnotationStatus": {item.value for item in DashboardAnnotationStatus},
    }
    for type_name, values in expected.items():
        assert _typescript_string_union(source, type_name) == values
