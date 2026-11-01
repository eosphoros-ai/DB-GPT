"""Range filters must bind endpoints rather than expanding a list into equality."""

from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.dashboard.query_executor import DashboardQueryExecutor
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardFilter,
    FilterParameterBinding,
)
from dbgpt_app.openapi.api_v1.dashboard.sql_security import DashboardSQLSecurityError
from dbgpt_app.openapi.api_v1.tools.dashboard import (
    _infer_filter_parameters,
    _validate_generated_filter_contract,
)


def range_schema(kind="number_range"):
    return SimpleNamespace(
        filters=[
            DashboardFilter(
                id="years",
                type=kind,
                label="Year",
                field="year",
                default=[2022, 2024]
                if kind == "number_range"
                else ["2022-01-01", "2024-12-31"],
            )
        ]
    )


@pytest.mark.parametrize(
    "binding",
    [
        "year",
        {"parameter": "year"},
        {"start_parameter": "year", "end_parameter": "year"},
        {"start_parameter": "lo"},
    ],
)
@pytest.mark.parametrize("kind", ["date_range", "number_range"])
def test_range_cannot_expand_into_a_scalar_predicate(kind, binding):
    with pytest.raises(DashboardSQLSecurityError, match="distinct start_parameter"):
        DashboardQueryExecutor._parameters_from_bindings(
            range_schema(kind),
            {},
            {},
            {"years": binding},
        )


@pytest.mark.parametrize(
    "supplied, expected",
    [
        ({}, {"lo": 2022, "hi": 2024}),
        ({"years": [2023, 2023]}, {"lo": 2023, "hi": 2023}),
        ({"years": None}, {"lo": None, "hi": None}),
    ],
)
def test_number_range_preserves_both_endpoints_and_user_override(supplied, expected):
    assert (
        DashboardQueryExecutor._parameters_from_bindings(
            range_schema(),
            supplied,
            {},
            {"years": FilterParameterBinding(start_parameter="lo", end_parameter="hi")},
        )
        == expected
    )


def test_number_range_inference_recognizes_min_max_without_changing_sql():
    plan = SimpleNamespace(filters=range_schema().filters)
    assert _infer_filter_parameters(
        "SELECT year FROM annual WHERE year BETWEEN :min_year AND :max_year",
        plan,
    ) == {"years": {"start_parameter": "min_year", "end_parameter": "max_year"}}


def test_null_all_option_cannot_replace_real_selectable_values():
    plan = SimpleNamespace(
        filters=[
            DashboardFilter(
                id="stores",
                type="multi_select",
                label="Store",
                field="store",
                options=[{"label": "All", "value": None}],
            )
        ]
    )
    with pytest.raises(ValueError, match="actual selectable values"):
        _validate_generated_filter_contract(plan, {"store"})
