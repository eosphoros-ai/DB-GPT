import pytest

from dbgpt_app.openapi.api_v1.dashboard.federation import (
    DashboardFederationService,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import FederatedQuery


def _source(alias):
    return {
        "alias": alias,
        "data_source_id": f"{alias}-db",
        "sql": "SELECT key, value FROM metrics",
        "column_mapping": {"key": "key", "value": alias},
    }


def test_union_result_is_bounded_before_it_is_returned():
    federation = FederatedQuery.model_validate(
        {
            "mode": "union_all",
            "sources": [_source("north"), _source("south")],
            "max_output_rows": 2,
        }
    )

    columns, rows, truncated = DashboardFederationService().combine(
        federation,
        {
            "north": [{"key": "A", "value": 1}, {"key": "B", "value": 2}],
            "south": [{"key": "C", "value": 3}],
        },
        ["key", "value"],
    )

    assert columns == ["key", "value"]
    assert rows == [["A", 1], ["B", 2]]
    assert truncated is True


def test_join_rejects_non_scalar_keys():
    federation = FederatedQuery.model_validate(
        {
            "mode": "join",
            "sources": [_source("left"), _source("right")],
            "join": {
                "left_alias": "left",
                "right_alias": "right",
                "left_field": "key",
                "right_field": "key",
                "join_type": "inner",
            },
        }
    )

    with pytest.raises(ValueError, match="must contain scalar values"):
        DashboardFederationService().combine(
            federation,
            {
                "left": [{"key": ["not", "scalar"], "left": 1}],
                "right": [{"key": "A", "right": 2}],
            },
            ["key", "left", "right"],
        )


def test_join_rejects_conflicting_output_values():
    federation = FederatedQuery.model_validate(
        {
            "mode": "join",
            "sources": [_source("left"), _source("right")],
            "join": {
                "left_alias": "left",
                "right_alias": "right",
                "left_field": "key",
                "right_field": "key",
                "join_type": "inner",
            },
        }
    )

    with pytest.raises(ValueError, match="conflicting output"):
        DashboardFederationService().combine(
            federation,
            {
                "left": [{"key": "A", "shared": 1}],
                "right": [{"key": "A", "shared": 2}],
            },
            ["key", "shared"],
        )
