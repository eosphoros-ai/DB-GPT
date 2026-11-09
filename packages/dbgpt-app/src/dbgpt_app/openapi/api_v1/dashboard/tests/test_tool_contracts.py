"""The model's inventory and structural contract must match registered tools."""

import re

import pytest

from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt.agent.resource import ToolPack
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardPlan,
    DashboardQueryDraftRequest,
)
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools
from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import (
    describe_registered_tools,
    make_dashboard_tool_pack,
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
    assert "load_dashboard_style:" not in description


def test_style_tool_loads_internal_reference_and_preserves_user_selection():
    state = {}
    tools = make_dashboard_planner_tools(
        react_state=state,
        database_connector=None,
        database_name=None,
        owner_id="alice",
        user_prompt="Build a marketing dashboard",
        model_name="test",
        stream_callback=None,
        gallery_template="catalog:store-marketing",
    )
    style = next(item for item in tools if item.__name__ == "load_dashboard_style")
    assert state["dashboard_gallery_context"]["skill"] == "dashboard-design"
    assert "Keep the user's selected" in style(
        selection="design:serenityspa-viz-design"
    )
    assert state["dashboard_gallery_context"]["selection"] == "catalog:store-marketing"


def test_style_tool_can_choose_a_reference_for_a_text_request():
    state = {}
    tools = make_dashboard_planner_tools(
        react_state=state,
        database_connector=None,
        database_name=None,
        owner_id="alice",
        user_prompt="Use a marketing style",
        model_name="test",
        stream_callback=None,
    )
    style = next(item for item in tools if item.__name__ == "load_dashboard_style")
    assert "catalog:store-marketing" in style()
    style(selection="catalog:store-marketing")
    assert state["dashboard_gallery_context"]["selection"] == "catalog:store-marketing"
    assert "could not be loaded" in style(selection="../../private")
    state["dashboard_record_id"] = "saved-plan"
    assert "persisted dashboard style" in style(selection="design:pawspa-viz-design")


@pytest.mark.asyncio
async def test_text_request_can_call_style_tool_through_actual_capability_pack():
    state = {}
    prompt = "Use a marketing style"
    tools = make_dashboard_planner_tools(
        state, None, None, "alice", prompt, "test", None
    )
    pack = make_dashboard_tool_pack(tools, prompt)
    inventory = await run_tool("load_dashboard_style", {}, pack)
    assert inventory.is_exe_success
    assert "catalog:store-marketing" in inventory.content
    selected = await run_tool(
        "load_dashboard_style", {"selection": "catalog:store-marketing"}, pack
    )
    assert selected.is_exe_success
    assert state["dashboard_gallery_context"]["selection"] == "catalog:store-marketing"
    assert state["dashboard_gallery_context"]["widgets"]


@pytest.mark.asyncio
async def test_exact_display_name_loads_style_without_a_discovery_round():
    state = {}
    prompt = "请用海报式营销样式生成看板"
    tools = make_dashboard_planner_tools(
        state, None, None, "alice", prompt, "test", None
    )
    pack = make_dashboard_tool_pack(tools, prompt)
    result = await run_tool("load_dashboard_style", {"selection": "海报式营销"}, pack)
    assert result.is_exe_success
    assert state["dashboard_gallery_context"]["selection"] == "design:brutal-viz-design"
    assert state["dashboard_gallery_context"]["widgets"]


@pytest.mark.parametrize(
    "prompt",
    [
        "[[confirm-dashboard:saved]]",
        "[[revise-dashboard-plan:saved]]",
        "[[modify-dashboard:saved]]",
        "[[dashboard-annotation:saved:annotation]]",
    ],
)
def test_later_phases_cannot_replace_the_saved_style(prompt):
    tools = make_dashboard_planner_tools(
        {},
        None,
        None,
        "alice",
        prompt,
        "test",
        None,
        gallery_template="design:pawspa-viz-design",
    )
    pack = make_dashboard_tool_pack(tools, prompt)
    assert "load_dashboard_style" not in {item.name for item in pack.sub_resources}


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
