"""Real planning regression: multilingual labels must not collapse into one id."""

import pytest

from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardPlan,
    collect_schema_issues,
)


@pytest.mark.parametrize(
    "labels",
    [
        ["总销售额（Weekly_Sales 求和）", "月度销售额（按年月汇总 Weekly_Sales）"],
        ["Revenue/Profit", "Revenue-Profit"],
        ["收入", "利润"],
        ["a" * 140 + "x", "a" * 140 + "y"],
    ],
)
def test_colliding_metric_and_dimension_labels_keep_distinct_references(labels):
    dimensions = (
        labels if sum(map(len, labels)) < 250 else ["Fiscal/year", "Fiscal-year"]
    )
    plan = DashboardPlan.model_validate(
        {
            "title": "经营分析",
            "business_theme": "保持用户请求的指标与维度",
            "metrics": labels,
            "dimensions": dimensions,
            "widgets": [
                {
                    "id": f"metric-{i}",
                    "type": "kpi",
                    "title": label,
                    "business_question": label,
                    "metric": label,
                    "dimensions": [dimensions[i]],
                }
                for i, label in enumerate(labels)
            ],
        }
    )
    schema = DashboardPlannerService(None)._build_schema(
        plan=plan,
        query_map={},
        data_source_id="sales",
        conversation_id="regression",
        prompt="Preserve both requested metrics",
        model_name="test",
    )
    assert collect_schema_issues(schema) == []
    assert len({item.id for item in schema.metric_context.metrics}) == len(labels)
    assert len({item.id for item in schema.metric_context.dimensions}) == len(labels)
    for i, widget in enumerate(schema.widgets):
        assert widget.metric_ids == [schema.metric_context.metrics[i].id]
        assert widget.dimension_ids == [schema.metric_context.dimensions[i].id]
        assert len(widget.metric_ids[0]) <= 128
