import json

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt.agent.resource import ToolPack
from dbgpt_app.openapi.api_v1.dashboard.confirmation import (
    DashboardConfirmationAgent,
    continuation_feedback,
    generation_failure,
    generation_start_event,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_app.openapi.api_v1.tools.dashboard import make_dashboard_planner_tools
from dbgpt_app.openapi.api_v1.tools.dashboard_contracts import make_dashboard_tool_pack

from .test_service import FakeConnector, FakeDao


@pytest.fixture
def environment():
    connector, dao = FakeConnector(), FakeDao()
    service = DashboardService(dao=dao, connector_resolver=lambda _: connector)
    events = []

    async def capture(kind, payload):
        events.append((kind, payload))

    def make(prompt, *, owner="alice", source="walmart"):
        state = {"conv_id": "confirmation-test"}
        tools = make_dashboard_planner_tools(
            state,
            connector,
            source,
            owner,
            prompt,
            "offline",
            capture,
            planner_service=DashboardPlannerService(service),
        )
        return state, ToolPack(tools)

    return make, dao, connector, events


async def planned(environment):
    make, dao, connector, events = environment
    state, pack = make("Build a dashboard")
    result = await run_tool(
        "plan_dashboard",
        {
            "plan": {
                "title": "Bound plan",
                "business_theme": "Retail",
                "metrics": ["sales"],
                "widgets": [
                    {
                        "id": f"sales-{i}",
                        "type": "kpi",
                        "title": f"Sales {i}",
                        "business_question": "How much?",
                        "metric": "sales",
                    }
                    for i in range(3)
                ],
            }
        },
        pack,
    )
    return json.loads(result.content)["__dashboard_plan_draft__"]["dashboard_id"]


def query(widget_id):
    return {
        "widget_id": widget_id,
        "sql": "SELECT SUM(sales) AS total_sales FROM sales",
        "output_fields": [{"name": "total_sales", "type": "number"}],
        "encoding": {"value": "total_sales"},
    }


@pytest.mark.asyncio
async def test_confirmation_rehydrates_and_completes_exact_plan_in_batches(environment):
    dashboard_id = await planned(environment)
    make, dao, connector, events = environment
    state, original_pack = make(
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    pack = make_dashboard_tool_pack(
        original_pack.sub_resources, f"[[confirm-dashboard:{dashboard_id}]]"
    )
    start = generation_start_event(state)
    assert start["dashboard_id"] == dashboard_id
    assert start["current_revision"] == 1
    assert start["total_widgets"] == 3
    assert start["plan"]["widgets"][2]["id"] == "sales-2"
    agent = DashboardConfirmationAgent(dashboard_state=state)
    first = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query("sales-0"), query("sales-1")]},
        },
        pack,
    )
    assert json.loads(first.content)["__dashboard_generation_staging__"][
        "missing_widget_ids"
    ] == ["sales-2"]
    assert dao.rows[dashboard_id].current_revision == 1
    assert connector.calls == []
    assert "sales-2" in continuation_feedback(state)
    assert "sales-0" not in continuation_feedback(state)
    early = await agent.act(
        AgentMessage(
            content='Thought: Done\nAction: terminate\nAction Input: {"result":"done"}'
        ),
        agent,
    )
    assert not early.terminate and not early.is_exe_success
    final = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query("sales-2")]},
        },
        pack,
    )
    assert json.loads(final.content)["__dashboard__"]["validated_widgets"] == 3
    assert state["dashboard_generation"]["status"] == "completed"
    assert continuation_feedback(state) is None
    assert generation_failure(state) is None
    assert dao.rows[dashboard_id].current_revision == 2
    assert len(dao.rows) == 1
    assert sum(kind == "dashboard.created" for kind, _ in events) == 1
    assert agent._dashboard_state is state
    assert agent.max_retry_count == 30
    assert len(ToolPack.from_resource(pack)) == 1
    agent.bind(AgentContext(conv_id="offline-confirmation"))
    for action in agent.actions:
        action.init_resource(pack)
    finished = await agent.act(
        AgentMessage(
            content='Thought: Done\nAction: terminate\nAction Input: {"result":"done"}'
        ),
        agent,
    )
    assert finished.terminate and finished.is_exe_success


@pytest.mark.asyncio
async def test_failed_component_stays_in_repair_stage_until_real_repair(environment):
    dashboard_id = await planned(environment)
    state, pack = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    broken = query("sales-2")
    broken["sql"] += " /* runtime_fail */"
    first = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query("sales-0"), query("sales-1"), broken]},
        },
        pack,
    )
    assert json.loads(first.content)["__dashboard__"]["failed_widgets"] == 1
    assert "repair_dashboard_draft" in continuation_feedback(state)
    assert state["dashboard_generation"]["failed_widget_ids"] == ["sales-2"]
    repaired = await run_tool(
        "repair_dashboard_draft",
        {
            "widget_queries": {
                "dashboard_id": dashboard_id,
                "widgets": [query("sales-2")],
            },
        },
        pack,
    )
    assert json.loads(repaired.content)["__dashboard__"]["failed_widgets"] == 0
    assert generation_failure(state) is None
    assert environment[1].rows[dashboard_id].current_revision == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["question", "terminate"])
async def test_premature_question_or_finish_cannot_end_confirmed_generation(
    environment, action
):
    dashboard_id = await planned(environment)
    state, _ = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    agent = DashboardConfirmationAgent(dashboard_state=state)
    output = await agent.act(
        AgentMessage(
            content=(
                f'Thought: Ask\nAction: {action}\nAction Input: {{"result":"请再确认"}}'
            )
        ),
        agent,
    )
    assert output.is_exe_success is False
    assert output.terminate is False
    assert "already confirmed" in output.content
    assert not any(kind == "question.asked" for kind, _ in environment[3])
    failure = generation_failure(state)
    assert failure["type"] == "dashboard.generation.failed"
    assert "未完成" in failure["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "variation",
    ["stale", "wrong-owner", "wrong-source", "missing-revision", "two-markers"],
)
async def test_invalid_confirmation_cannot_rebind_or_run_sql(environment, variation):
    dashboard_id = await planned(environment)
    make, dao, connector, _ = environment
    kwargs = {}
    prompt = f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    if variation == "stale":
        dao.rows[dashboard_id].current_revision = 2
    elif variation == "wrong-owner":
        kwargs["owner"] = "bob"
    elif variation == "wrong-source":
        kwargs["source"] = "other"
    elif variation == "missing-revision":
        prompt = f"[[confirm-dashboard:{dashboard_id}]] confirm"
    else:
        prompt += f" [[confirm-dashboard:{dashboard_id}]]"
    state, pack = make(prompt, **kwargs)
    assert state.get("dashboard_confirmation_error")
    assert generation_start_event(state) is None
    revision = dao.rows[dashboard_id].current_revision
    result = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": revision,
            "widget_queries": {"widgets": [query("sales-0")]},
        },
        pack,
    )
    assert "__dashboard__" not in json.loads(result.content)
    assert dao.rows[dashboard_id].current_revision == revision
    assert connector.calls == []


@pytest.mark.asyncio
async def test_edit_during_confirmation_is_checked_before_staging(environment):
    dashboard_id = await planned(environment)
    make, dao, connector, _ = environment
    state, pack = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1")
    dao.rows[dashboard_id].current_revision = 2
    result = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 2,
            "widget_queries": {"widgets": [query("sales-0")]},
        },
        pack,
    )
    assert "plan changed" in result.content.lower()
    assert "dashboard_query_staging" not in state
    assert connector.calls == []


@pytest.mark.asyncio
async def test_completed_plan_cannot_be_confirmed_twice(environment):
    dashboard_id = await planned(environment)
    make, dao, connector, _ = environment
    _, pack = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1")
    await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query(f"sales-{i}") for i in range(3)]},
        },
        pack,
    )
    before = list(connector.calls)
    state, replay = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 2")
    assert state.get("dashboard_confirmation_error")
    assert generation_start_event(state) is None
    result = await run_tool(
        "create_dashboard_draft",
        {"widget_queries": {"widgets": [query("sales-0")]}},
        replay,
    )
    assert "__dashboard__" not in json.loads(result.content)
    assert connector.calls == before
    assert dao.rows[dashboard_id].current_revision == 2


def test_ordinary_planning_and_explanation_do_not_acquire_generation_guard():
    assert continuation_feedback({}) is None
    assert generation_start_event({}) is None
    assert generation_failure({}) is None
