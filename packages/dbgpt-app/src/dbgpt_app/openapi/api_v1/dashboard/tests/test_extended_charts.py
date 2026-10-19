import pytest

from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardSchemaV1,
    collect_schema_issues,
)

from .test_schema import valid_schema_dict


@pytest.mark.parametrize(
    "visualization", ["funnel", "treemap", "radar", "waterfall", "geo_map"]
)
def test_extended_visualizations_preserve_query_contract(visualization):
    payload = valid_schema_dict()
    payload["schema_version"] = "1.4"
    payload["dashboard"]["theme"] = {"preset": "clarity", "mode": "light"}
    payload["widgets"][0]["presentation"] = {"visualization": visualization}
    schema = DashboardSchemaV1.model_validate(payload)
    assert not collect_schema_issues(schema)
    round_trip = DashboardSchemaV1.model_validate(schema.model_dump(mode="json"))
    assert round_trip.widgets[0].presentation.visualization.value == visualization
    schema.widgets[0].encoding.y = None
    assert any(
        issue.code == "missing_encoding" for issue in collect_schema_issues(schema)
    )
