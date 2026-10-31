import json
from unittest.mock import AsyncMock

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt.agent.expand.react_agent import ReActAgent
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.util.react_parser import extract_terminate_output
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


async def planned(environment, *, count=3):
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
                    for i in range(count)
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


def bound_agent(state, pack):
    agent = DashboardConfirmationAgent(dashboard_state=state)
    agent.bind(AgentContext(conv_id="offline-performance"))
    for action in agent.actions:
        action.init_resource(pack)
    return agent


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["zh", "en"])
async def test_saved_plan_finishes_without_another_model_call(
    environment, monkeypatch, language
):
    state, pack = environment[0]("Build a dashboard")
    state["_report_language"] = language
    agent = bound_agent(state, pack)
    output = await agent.act(
        AgentMessage(
            model_name="offline",
            content="Thought: Plan\nAction: plan_dashboard\nAction Input: "
            + json.dumps(
                {
                    "plan": {
                        "title": "Sales",
                        "business_theme": "Retail",
                        "metrics": ["sales"],
                        "widgets": [
                            {
                                "id": "sales-0",
                                "type": "kpi",
                                "title": "Sales",
                                "business_question": "How much?",
                                "metric": "sales",
                            }
                        ],
                    }
                }
            ),
        ),
        agent,
    )
    assert output.is_exe_success and not output.terminate
    assert output.action == "plan_dashboard"  # Preserve the real tool step.
    model = AsyncMock(side_effect=AssertionError("Unnecessary model call"))
    monkeypatch.setattr(ReActAgent, "thinking", model)
    reply, model_name = await agent.thinking([], agent)
    assert model_name == "offline"
    summary = extract_terminate_output(reply)
    assert ("规划已保存" if language == "zh" else "Plan") in summary
    finished = await agent.act(AgentMessage(content=reply), agent)
    assert finished.terminate and finished.is_exe_success
    model.assert_not_awaited()
    assert environment[2].calls == []  # Planning still never generates widget SQL.
    assert environment[1].rows[state["dashboard_record_id"]].current_revision == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["staging", "repair", "completed"])
async def test_only_validated_saved_generation_skips_final_model_call(
    environment, monkeypatch, phase
):
    dashboard_id = await planned(environment)
    state, pack = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    agent = bound_agent(state, pack)
    widgets = [query(f"sales-{i}") for i in range(2 if phase == "staging" else 3)]
    if phase == "repair":
        widgets[-1]["sql"] += " /* runtime_fail */"
    output = await agent.act(
        AgentMessage(
            model_name="offline",
            content="Thought: Generate\nAction: create_dashboard_draft\nAction Input: "
            + json.dumps(
                {
                    "dashboard_id": dashboard_id,
                    "expected_revision": 1,
                    "widget_queries": {"widgets": widgets},
                }
            ),
        ),
        agent,
    )
    assert output.action == "create_dashboard_draft" and not output.terminate
    model = AsyncMock(return_value=("continue generation", "offline"))
    monkeypatch.setattr(ReActAgent, "thinking", model)
    reply, _ = await agent.thinking([], agent)
    if phase == "completed":
        assert "All 3 widgets passed" in extract_terminate_output(reply)
        assert generation_failure(state) is None
        model.assert_not_awaited()
    else:
        assert reply == "continue generation"
        assert generation_failure(state) is not None
        model.assert_awaited_once()


@pytest.mark.asyncio
async def test_four_widget_batches_still_save_only_after_all_queries(environment):
    dashboard_id = await planned(environment, count=5)
    make, dao, connector, events = environment
    state, pack = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1")
    create_tool = next(
        t for t in pack.sub_resources if t.name == "create_dashboard_draft"
    )
    assert "at most 4 widgets" in create_tool.description
    first = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query(f"sales-{i}") for i in range(4)]},
        },
        pack,
    )
    staging = json.loads(first.content)["__dashboard_generation_staging__"]
    assert staging["max_widgets_per_call"] == 4
    assert staging["missing_widget_ids"] == ["sales-4"]
    assert "at most 4 missing widgets" in continuation_feedback(state)
    assert connector.calls == []
    assert dao.rows[dashboard_id].current_revision == 1
    await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query("sales-4")]},
        },
        pack,
    )
    assert state["dashboard_generation"]["status"] == "completed"
    assert dao.rows[dashboard_id].current_revision == 2
    assert len(json.loads(dao.rows[dashboard_id].schema_json)["widgets"]) == 5
    assert sum(kind == "dashboard.created" for kind, _ in events) == 1


@pytest.mark.asyncio
async def test_truncated_query_payload_reduces_following_batches(environment):
    dashboard_id = await planned(environment)
    make, dao, connector, _ = environment
    state, pack = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1")
    broken = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": '{"widgets":[',
        },
        pack,
    )
    assert "truncated or malformed" in broken.content
    assert "at most 2 missing widgets" in continuation_feedback(state)
    assert connector.calls == []
    first = await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query("sales-0"), query("sales-1")]},
        },
        pack,
    )
    assert (
        json.loads(first.content)["__dashboard_generation_staging__"][
            "max_widgets_per_call"
        ]
        == 2
    )
    assert dao.rows[dashboard_id].current_revision == 1
    await run_tool(
        "create_dashboard_draft",
        {
            "dashboard_id": dashboard_id,
            "expected_revision": 1,
            "widget_queries": {"widgets": [query("sales-2")]},
        },
        pack,
    )
    assert generation_failure(state) is None
    assert dao.rows[dashboard_id].current_revision == 2


def test_filtered_plan_keeps_small_query_contract():
    state = {"dashboard_plan": {"filters": [{"id": "store", "type": "select"}]}}
    tools = make_dashboard_planner_tools(
        state, None, None, "alice", "Build a dashboard", "offline", None
    )
    create_tool = next(
        t for t in ToolPack(tools).sub_resources if t.name == "create_dashboard_draft"
    )
    assert "at most 2 widgets" in create_tool.description
    assert "At most 2 widgets" in create_tool.args["widget_queries"].description


@pytest.mark.asyncio
async def test_confirmation_retains_scope_empty_results_and_filter_defaults(
    environment,
):
    make, _, connector, _ = environment
    _, pack = make("Review January sales for stores 1 and 2")
    result = await run_tool(
        "plan_dashboard",
        {
            "plan": {
                "title": "January sales",
                "business_theme": "Retail",
                "description": "Only January 2026; never substitute another year.",
                "decision_goal": "Find stores without sales in the requested period.",
                "analysis_logic": ["Keep genuine empty results visible."],
                "filter_strategy": "Default to stores 1 and 2 and January 2026.",
                "metrics": ["sales"],
                "dimensions": ["store", "date"],
                "filters": [
                    {
                        "id": "stores",
                        "type": "multi_select",
                        "label": "Stores",
                        "field": "store",
                        "default": [1, 2],
                        "options": [
                            {"label": "Store 1", "value": 1},
                            {"label": "Store 2", "value": 2},
                        ],
                    },
                    {
                        "id": "period",
                        "type": "date_range",
                        "label": "Period",
                        "field": "date",
                        "default": ["2026-01-01", "2026-01-31"],
                    },
                    {
                        "id": "recent",
                        "type": "date_range",
                        "label": "Recent week",
                        "field": "date",
                        "default": ["2026-01-25", "2026-01-31"],
                        "relative_date": {
                            "start_offset_days": -6,
                            "end_offset_days": 0,
                        },
                    },
                ],
                "widgets": [
                    {
                        "id": "empty-sales",
                        "type": "table",
                        "title": "Sales in January 2026",
                        "business_question": "Did stores 1 and 2 have January sales?",
                        "metric": "sales",
                        "dimensions": ["store", "date"],
                        "expected_data_points": 0,
                        "rationale": "The requested period has no observations.",
                    }
                ],
            }
        },
        pack,
    )
    assert result.is_exe_success
    assert "__dashboard_plan_draft__" in json.loads(result.content), result.content
    dashboard_id = json.loads(result.content)["__dashboard_plan_draft__"][
        "dashboard_id"
    ]
    state, _ = make(f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1")
    contract = state["dashboard_confirmation_contract"]
    scope = contract["business_scope"]
    assert "Only January 2026" in scope["description"]
    assert "without sales" in scope["decision_goal"]
    assert scope["analysis_logic"] == ["Keep genuine empty results visible."]
    assert scope["filter_strategy"] == "Default to stores 1 and 2 and January 2026."
    assert scope["metrics"] == ["sales"]
    assert scope["dimensions"] == ["store", "date"]
    widget = contract["widgets"][0]
    assert widget["expected_data_points"] == 0
    assert widget["type"] == "table"
    assert "stores 1 and 2" in widget["business_question"]
    assert "no observations" in widget["rationale"]
    filters = {item["filter_id"]: item for item in contract["filters"]}
    assert filters["stores"]["default"] == [1, 2]
    assert filters["stores"]["options"][1] == {"label": "Store 2", "value": 2}
    assert filters["period"]["default"] == ["2026-01-01", "2026-01-31"]
    assert filters["recent"]["relative_date"] == {
        "anchor": "today",
        "start_offset_days": -6,
        "end_offset_days": 0,
    }
    assert connector.calls == []


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
@pytest.mark.parametrize(
    "action", ["sql_query", "load_dashboard_style", "plan_dashboard"]
)
async def test_wrong_phase_action_can_recover_without_executing_it(environment, action):
    dashboard_id = await planned(environment)
    prompt = f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    state, original_pack = environment[0](prompt)
    pack = make_dashboard_tool_pack(original_pack.sub_resources, prompt)
    agent = bound_agent(state, pack)
    denied = await agent.act(
        AgentMessage(
            content=f"Thought: Explore again\nAction: {action}\nAction Input: {{}}"
        ),
        agent,
    )
    assert not denied.is_exe_success and not denied.terminate
    assert denied.have_retry
    assert "unavailable during confirmed generation" in denied.content
    assert "create_dashboard_draft" in denied.content
    assert environment[2].calls == []
    assert "dashboard_tool_failure" not in state
    assert environment[1].rows[dashboard_id].current_revision == 1

    payload = {
        "dashboard_id": dashboard_id,
        "expected_revision": 1,
        "widget_queries": {"widgets": [query(f"sales-{i}") for i in range(3)]},
    }
    completed = await agent.act(
        AgentMessage(
            content="Thought: Generate confirmed queries\n"
            "Action: create_dashboard_draft\n"
            "Action Input: " + json.dumps(payload)
        ),
        agent,
    )
    assert completed.is_exe_success
    assert state["dashboard_generation"]["status"] == "completed"
    assert generation_failure(state) is None
    assert len(environment[1].rows) == 1
    assert environment[1].rows[dashboard_id].current_revision == 2


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
