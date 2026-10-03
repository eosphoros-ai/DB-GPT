"""The model's inventory and structural contract must match registered tools."""

import re

from dbgpt.agent.resource import ToolPack
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardPlan,
    DashboardQueryDraftRequest,
)
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools
from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import (
    describe_registered_tools,
    validation_model_contracts,
)


def _tools(prompt="Build a dashboard"):
    return make_dashboard_planner_tools(
        react_state={},
        database_connector=None,
        database_name=None,
        owner_id="alice",
        user_prompt=prompt,
        model_name="test",
        stream_callback=None,
    )


def test_inventory_matches_every_registered_tool_including_load():
    pack = ToolPack(_tools())
    description = describe_registered_tools(pack)
    displayed = set(re.findall(r"^- ([a-z_]+):", description, re.MULTILINE))
    assert displayed == {resource.name for resource in pack.sub_resources}
    assert "load_dashboard_draft" in displayed
    assert '"widget_queries":{"type":"object"' in description
    assert '"plan":{"type":"object"' in description


def test_read_only_inventory_does_not_advertise_generation():
    pack = ToolPack(_tools("[[dashboard-annotation:dash:annotation]] [异常分析]"))
    description = describe_registered_tools(pack)
    assert "load_dashboard_draft" in description
    assert "create_dashboard_draft:" not in description
    assert "DashboardQueryDraftRequest =" not in description


def test_generated_shapes_preserve_required_fields_enums_and_nested_contracts():
    description = validation_model_contracts(
        [DashboardPlan, DashboardQueryDraftRequest]
    )
    assert "business_theme!: string" in description
    assert "metrics!: array<string>" in description
    assert "audience?: string" in description
    assert "output_fields!: array<QueryOutputField>" in description
    assert (
        "filter_parameters?: map<string, string | FilterParameterBinding>"
        in description
    )
    assert "publication?: DashboardPublicationDraft | null" in description
    assert "output_columns?: array<string>" in description
    assert '"maximum":5000' in description
    assert 'DataFieldType = "string" | "number" | "integer"' in description
    assert description.count("QueryOutputField =") == 1
