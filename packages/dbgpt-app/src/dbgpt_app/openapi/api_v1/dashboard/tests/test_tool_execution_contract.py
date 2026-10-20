"""Exercise the same pack/repack/dispatch boundary as a real ReAct call."""

import json

import pytest

from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.resource.tool.base import tool
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools
from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import (
    describe_registered_tools,
    make_dashboard_tool_pack,
)
from dbgpt_app.openapi.api_v1.tools.question import make_question
from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query

from .test_service import FakeConnector, FakeDao


def _pack(resources, prompt):
    return make_dashboard_tool_pack(resources, prompt)


@pytest.fixture
def tool_environment():
    connector, dao = FakeConnector(), FakeDao()
    service = DashboardService(dao=dao, connector_resolver=lambda _: connector)
    events = []

    async def capture(kind, payload):
        events.append((kind, payload))

    def make(prompt):
        return _pack(
            make_dashboard_planner_tools(
                react_state={"conv_id": "contract-dispatch"},
                database_connector=connector,
                database_name="walmart",
                owner_id="alice",
                user_prompt=prompt,
                model_name="offline-test",
                stream_callback=capture,
                planner_service=DashboardPlannerService(service),
            ),
            prompt,
        )

    return make, dao, connector, events


async def _confirmed(tool_environment):
    make, dao, connector, events = tool_environment
    planning = await run_tool(
        "plan_dashboard",
        {
            "plan": {
                "title": "Sales",
                "business_theme": "Retail",
                "metrics": ["sales"],
                "widgets": [
                    {
                        "id": "sales",
                        "type": "kpi",
                        "title": "Sales",
                        "business_question": "How much?",
                        "metric": "sales",
                    }
                ],
            }
        },
        make("Build a dashboard"),
    )
    planned = json.loads(planning.content)
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]
    pack = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1")
    args = {
        "dashboard_id": dashboard_id,
        "expected_revision": 1,
        "widget_queries": {
            "widgets": [
                {
                    "widget_id": "sales",
                    "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                }
            ]
        },
    }
    return pack, args


@pytest.mark.asyncio
@pytest.mark.parametrize("with_valid_wrapper", [False, True])
async def test_misplaced_widgets_are_rejected_before_execution(
    tool_environment, with_valid_wrapper
):
    pack, args = await _confirmed(tool_environment)
    make, dao, connector, events = tool_environment
    original = json.loads(json.dumps(args))
    args["widgets"] = args["widget_queries"]["widgets"]
    if not with_valid_wrapper:
        args.pop("widget_queries")
    before_calls = list(connector.calls)
    # run_tool reconstructs ToolPack from resources; a pack-only override is lost.
    outcome = await run_tool(
        "create_dashboard_draft", args, pack, raw_tool_input=json.dumps(args)
    )
    assert outcome.is_exe_success is False, outcome.content
    assert "Unknown top-level" in outcome.content
    assert "widget_queries.widgets" in outcome.content
    assert dao.rows[original["dashboard_id"]].current_revision == 1
    assert connector.calls == before_calls
    assert not any(kind == "dashboard.created" for kind, _ in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_alias", [False, True])
async def test_canonical_and_existing_alias_reach_real_validation(
    tool_environment, legacy_alias
):
    pack, args = await _confirmed(tool_environment)
    if legacy_alias:
        args["draft"] = json.dumps(args.pop("widget_queries"))
    outcome = await run_tool(
        "create_dashboard_draft", args, pack, raw_tool_input=json.dumps(args)
    )
    payload = json.loads(outcome.content)
    assert payload["__dashboard__"]["dashboard_id"] == args["dashboard_id"]
    assert tool_environment[1].rows[args["dashboard_id"]].current_revision == 2
    assert tool_environment[2].calls


@pytest.mark.asyncio
async def test_non_dashboard_tools_keep_existing_unknown_argument_behavior():
    @tool(description="Return the value.")
    def echo(value: str):
        return value

    outcome = await run_tool(
        "echo", {"value": "ok", "ignored": "legacy"}, ToolPack([echo])
    )
    assert outcome.is_exe_success
    assert outcome.content == "ok"


@pytest.mark.parametrize(
    "prompt,read_only,expected",
    [
        (
            "Build a dashboard",
            False,
            {
                "plan_dashboard",
                "sql_query",
                "load_dashboard_draft",
                "resolve_dashboard_reference",
                "modify_dashboard_draft",
            },
        ),
        (
            "请生成 2030 年看板，不要改成有记录的年份",
            False,
            {
                "plan_dashboard",
                "sql_query",
                "load_dashboard_draft",
                "resolve_dashboard_reference",
                "modify_dashboard_draft",
            },
        ),
        (
            "继续修改现有看板 c852b9417fea4b5ebcdf933df452857a",
            False,
            {
                "plan_dashboard",
                "sql_query",
                "load_dashboard_draft",
                "resolve_dashboard_reference",
                "modify_dashboard_draft",
            },
        ),
        (
            "[[confirm-dashboard:example]] confirm revision 1",
            False,
            {
                "load_dashboard_draft",
                "create_dashboard_draft",
                "repair_dashboard_draft",
            },
        ),
        (
            "[[revise-dashboard-plan:example]] revise",
            False,
            {"load_dashboard_draft", "revise_dashboard_plan"},
        ),
        (
            "[[modify-dashboard:example]] modify",
            False,
            {
                "load_dashboard_draft",
                "resolve_dashboard_reference",
                "modify_dashboard_draft",
                "repair_dashboard_draft",
                "sql_query",
            },
        ),
        (
            "[[dashboard-annotation:example:annotation]] [修改组件]",
            False,
            {
                "load_dashboard_draft",
                "resolve_dashboard_reference",
                "propose_dashboard_change",
            },
        ),
        (
            "[[dashboard-annotation:example:annotation]] [异常分析]",
            True,
            {"load_dashboard_draft", "resolve_dashboard_reference"},
        ),
    ],
)
def test_inventory_is_scoped_to_actual_capabilities(prompt, read_only, expected):
    # Supply the whole factory output, including mutations, to test the final
    # permission boundary independently of the factory's own read-only filter.
    resources = make_dashboard_planner_tools(
        {}, None, None, "alice", "Build a dashboard", "offline", None
    )
    resources += [make_sql_query({}, None), make_question({}, None), Terminate()]
    pack = make_dashboard_tool_pack(resources, prompt, read_only_annotation=read_only)
    assert {r.name for r in pack.sub_resources} == expected | {"question", "terminate"}
    description = describe_registered_tools(pack)
    for resource in pack.sub_resources:
        assert f"- {resource.name}:" in description
        assert resource.description not in description  # supplied once by ReAct
    assert ("DashboardPlan =" in description) == bool(
        expected & {"plan_dashboard", "revise_dashboard_plan"}
    )
    assert ("DashboardQueryDraftRequest =" in description) == bool(
        expected & {"create_dashboard_draft", "repair_dashboard_draft"}
    )


@pytest.mark.asyncio
async def test_unknown_argument_failure_never_echoes_values(tool_environment):
    pack, args = await _confirmed(tool_environment)
    args["mistyped"] = "private-value-do-not-echo"
    outcome = await run_tool("create_dashboard_draft", args, pack)
    assert not outcome.is_exe_success
    assert "mistyped" in outcome.content
    assert "private-value-do-not-echo" not in outcome.content
