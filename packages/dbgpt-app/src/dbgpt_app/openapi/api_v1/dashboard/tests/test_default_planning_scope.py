"""Broad overview plans must be corrected before creating a saved asset."""

import pytest

from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt_app.openapi.api_v1.tools.dashboard import (
    _is_broad_dashboard_request,
    make_dashboard_planner_tools,
)
from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import make_dashboard_tool_pack


@pytest.mark.parametrize(
    "prompt",
    [
        "构建销售经营大盘，给运营负责人看，按周监控销售趋势和门店表现",
        "[Database: retail] 构建经营仪表板，按月看区域销售",
        "Build a sales dashboard for weekly revenue and store performance",
    ],
)
def test_short_overview_uses_default_scope(prompt):
    assert _is_broad_dashboard_request(prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "构建经营大盘，包括销售、利润、退款、库存、客户五个指标",
        "构建经营大盘，添加门店筛选",
        "构建经营大盘，需要 8 个组件",
        "Build a sales dashboard including five charts and region filters",
        "销售趋势、利润趋势、退款趋势、客户分布、库存明细",
    ],
)
def test_explicit_requirements_keep_their_scope(prompt):
    assert not _is_broad_dashboard_request(prompt)


@pytest.mark.asyncio
@pytest.mark.parametrize("extra_filters", [False, True])
async def test_oversized_or_filtered_overview_is_not_saved(extra_filters):
    state = {}
    events = []

    async def capture(kind, payload):
        events.append((kind, payload))

    prompt = "构建销售经营大盘，按周监控销售趋势和门店表现"
    tools = make_dashboard_planner_tools(
        state, object(), "retail", "alice", prompt, "offline", capture
    )
    plan = {
        "title": "Sales",
        "business_theme": "Retail",
        "audience": "Operations",
        "decision_goal": "Monitor sales",
        "analysis_logic": ["Monitor weekly revenue"],
        "layout_rationale": "Overview",
        "filter_strategy": "None",
        "metrics": ["revenue"],
        "dimensions": ["store"],
        "filters": (
            [{"id": "store", "type": "select", "label": "Store", "field": "store"}]
            if extra_filters
            else []
        ),
        "widgets": [
            {
                "id": f"metric-{index}",
                "type": "kpi",
                "title": f"Metric {index}",
                "business_question": "How much revenue?",
                "metric": "SUM(revenue)",
                "dimensions": [],
                "analysis_level": 1,
                "rationale": "Overview",
                "layout": {"width": "third", "height": "compact"},
            }
            for index in range(3 if extra_filters else 7)
        ],
    }
    result = await run_tool(
        "plan_dashboard", {"plan": plan}, make_dashboard_tool_pack(tools, prompt)
    )
    assert "scope validation failed" in result.content
    assert not events
    assert "dashboard_record_id" not in state
