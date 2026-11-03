"""Real ReAct dispatch must stop failed tools before a technical question can run."""

import json
import sqlite3

import pytest

from dbgpt.agent import ActionOutput, AgentContext, AgentMessage
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.resource.tool.base import tool
from dbgpt_app.openapi.api_v1.dashboard.confirmation import (
    DashboardConfirmationAgent,
    generation_failure,
)
from dbgpt_app.openapi.api_v1.dashboard.tool_failure import (
    capture_tool_failure,
    discovery_correction,
)
from dbgpt_app.openapi.api_v1.tools.question import make_question
from dbgpt_app.openapi.api_v1.tools.question_manager import question_manager
from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query

from .test_proposal_tool_contract import _proposal
from .test_proposal_tool_contract import (
    annotation_services as _annotation_services_fixture,
)

annotation_services = _annotation_services_fixture


def test_generation_parse_failure_closes_the_matching_board_card():
    state = {
        "conv_id": "conversation",
        "dashboard_generation": {
            "dashboard_id": "sales",
            "source_turn_id": "planning-turn",
            "generation_id": "run-1",
            "total_widgets": 4,
        },
    }
    failure = capture_tool_failure(
        state, ActionOutput(is_exe_success=False, content="Invalid model response")
    )
    assert failure["dashboard_id"] == "sales"
    assert failure["source_turn_id"] == "planning-turn"
    assert failure["generation_id"] == "run-1"
    assert failure["editor_path"] == "/dashboards/sales"


def bound_agent(state, tools):
    agent = DashboardConfirmationAgent(dashboard_state=state)
    agent.bind(AgentContext(conv_id=state["conv_id"]))
    pack = ToolPack(tools)
    for action in agent.actions:
        action.init_resource(pack)
    return agent


@pytest.mark.asyncio
async def test_native_dashboard_call_dispatches_without_text_react():
    calls = []

    @tool(description="Inspect sales", args={})
    async def inspect_sales():
        calls.append("inspect")
        return {"rows": 10}

    agent = bound_agent({"conv_id": "native-dashboard"}, [inspect_sales])
    agent.bind(ToolPack([inspect_sales]))
    agent.bind(
        AgentContext(conv_id="native-dashboard", enable_native_function_calling=True)
    )
    object.__setattr__(
        agent,
        "_pending_native_tool_calls",
        [
            {
                "id": "call-sales",
                "type": "function",
                "function": {"name": "inspect_sales", "arguments": "{}"},
            }
        ],
    )
    output = await agent.act(
        AgentMessage(content="检查销售数据。"),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert output.is_exe_success
    assert calls == ["inspect"]
    assert any(
        item["function"]["name"] == "inspect_sales"
        for item in agent._build_native_tools()
    )


@pytest.mark.asyncio
async def test_saved_complete_generation_ends_without_another_provider_call():
    state = {
        "conv_id": "persisted-completion",
        "dashboard_generation": {
            "dashboard_id": "sales",
            "status": "generating",
            "current_revision": 1,
        },
        "dashboard_plan": {"widgets": [{"id": "total"}]},
        "dashboard_confirmation_contract": {"widgets": [{"widget_id": "total"}]},
    }

    @tool(description="Save a validated revision", args={})
    async def save_validated():
        state["dashboard_generation"].update(status="completed", saved_revision=2)
        return {"saved_revision": 2}

    agent = bound_agent(state, [save_validated])
    output = await act(agent, "save_validated", {})
    assert output.is_exe_success and output.terminate
    assert "dashboard_tool_failure" not in state


@pytest.mark.asyncio
async def test_saved_plan_ends_before_waiting_for_another_provider_response():
    state = {"conv_id": "persisted-plan"}

    @tool(description="Save a plan for confirmation", args={})
    async def plan_dashboard():
        state.update(
            dashboard_record_id="sales",
            dashboard_refs=[
                {"dashboard_id": "sales", "status": "awaiting_confirmation"}
            ],
        )
        return {"saved_revision": 1}

    agent = bound_agent(state, [plan_dashboard])
    output = await act(agent, "plan_dashboard", {})
    assert output.is_exe_success and output.terminate


@pytest.mark.asyncio
async def test_native_terminate_cannot_finish_incomplete_dashboard():
    state = {
        "conv_id": "native-confirmation",
        "dashboard_generation": {
            "dashboard_id": "sales",
            "status": "running",
            "current_revision": 1,
        },
        "dashboard_plan": {"widgets": []},
        "dashboard_confirmation_contract": {"widgets": [{"widget_id": "trend"}]},
    }
    agent = bound_agent(state, [])
    object.__setattr__(
        agent,
        "_pending_native_tool_calls",
        [{"function": {"name": "terminate", "arguments": '{"output":"done"}'}}],
    )
    output = await agent.act(AgentMessage(content=""), agent)
    assert not output.is_exe_success and not output.terminate
    assert "trend" in output.content
    assert "dashboard_tool_failure" not in state


@pytest.mark.asyncio
async def test_plain_response_continues_staged_generation_with_bounded_retries():
    staged = {"widgets": {"total": {"sql": "SELECT SUM(sales) FROM orders"}}}
    state = {
        "conv_id": "partial-native-response",
        "dashboard_generation": {
            "dashboard_id": "sales",
            "status": "running",
            "current_revision": 1,
        },
        "dashboard_plan": {"widgets": [{"id": "total"}, {"id": "trend"}]},
        "dashboard_confirmation_contract": {
            "widgets": [{"widget_id": "total"}, {"widget_id": "trend"}]
        },
        "dashboard_query_staging": staged,
    }
    agent = bound_agent(state, [])
    agent.bind(
        AgentContext(conv_id=state["conv_id"], enable_native_function_calling=True)
    )
    for _ in range(2):
        output = await agent.act(AgentMessage(content="看板已完成。"), agent)
        assert not output.is_exe_success and output.have_retry
        assert not output.terminate
        assert "at most two missing widgets: trend" in output.content
        assert state["dashboard_query_staging"] is staged
        assert "dashboard_tool_failure" not in state
    output = await agent.act(AgentMessage(content="看板已完成。"), agent)
    assert not output.is_exe_success and not output.have_retry
    assert "dashboard_tool_failure" in state
    assert state["dashboard_query_staging"] is staged


async def act(agent, name, arguments):
    return await agent.act(
        AgentMessage(
            content=(
                f"Thought: Execute\nAction: {name}\nAction Input: "
                + json.dumps(arguments, ensure_ascii=False)
            )
        ),
        agent,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("saved", [False, True])
@pytest.mark.parametrize("status", ["awaiting_confirmation", "updated"])
async def test_plain_completion_requires_persisted_plan(saved, status):
    state = {"conv_id": "plain-completion"}
    if saved:
        state.update(
            dashboard_record_id="sales",
            dashboard_refs=[
                {
                    "dashboard_id": "sales",
                    "title": "Sales",
                    "status": status,
                    "current_revision": 2,
                }
            ],
        )
    agent = bound_agent(state, [])
    agent.bind(
        AgentContext(conv_id=state["conv_id"], enable_native_function_calling=True)
    )
    output = await agent.act(
        AgentMessage(content="看板已经发布，全部工作完成。"), agent
    )
    assert output.is_exe_success is saved
    if saved:
        assert output.terminate
        assert "修订 2" in output.content
        assert ("规划" if status == "awaiting_confirmation" else "草稿修改") in (
            output.content
        )
        assert "已经发布" not in output.content
        assert "dashboard_tool_failure" not in state
    else:
        assert "dashboard_tool_failure" in state


@pytest.mark.asyncio
async def test_plain_planning_response_recovers_only_after_real_successful_query():
    class SqliteConnector:
        dialect = "sqlite"

        def run(self, sql):
            with sqlite3.connect(":memory:") as connection:
                cursor = connection.execute(sql)
                return [cursor.description, *cursor.fetchall()]

    state = {"conv_id": "planning-native-response"}
    agent = bound_agent(state, [make_sql_query(state, SqliteConnector(), max_calls=8)])
    queried = await act(agent, "sql_query", {"sql": "SELECT 42 AS total_sales"})
    assert queried.is_exe_success
    agent.bind(
        AgentContext(conv_id=state["conv_id"], enable_native_function_calling=True)
    )
    for _ in range(2):
        output = await agent.act(AgentMessage(content="我将生成看板。"), agent)
        assert not output.is_exe_success and output.have_retry
        assert "Call plan_dashboard" in output.content
        assert "dashboard_tool_failure" not in state
    output = await agent.act(AgentMessage(content="我将生成看板。"), agent)
    assert not output.have_retry
    assert "dashboard_tool_failure" in state


@pytest.mark.asyncio
async def test_actual_sqlite_catalog_failure_can_be_corrected():
    class SqliteConnector:
        dialect = "sqlite"

        def run(self, sql):
            with sqlite3.connect(":memory:") as connection:
                cursor = connection.execute(sql)
                return [cursor.description, *cursor.fetchall()]

    state = {"conv_id": "actual-sqlite-correction", "database_name": "Walmart_Sales"}
    agent = bound_agent(state, [make_sql_query(state, SqliteConnector(), max_calls=8)])
    failed = await act(
        agent,
        "sql_query",
        {"sql": "SELECT * FROM information_schema.columns"},
    )
    assert failed.have_retry and not failed.is_exe_success
    evidence = json.loads(failed.observations)
    assert evidence["chunks"][1]["content"]["execution"]["status"] == "failed"
    corrected = await act(agent, "sql_query", {"sql": "SELECT 42 AS total_sales"})
    assert corrected.is_exe_success
    assert json.loads(corrected.content)["chunks"][0]["content"]["rows"] == [[42]]
    assert "dashboard_tool_failure" not in state


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed_success", [False, True])
async def test_native_parallel_sqlite_discovery_recovers_real_results(
    tmp_path, mixed_success
):
    path = tmp_path / "sales.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE walmart_sales (Weekly_Sales REAL)")
        connection.executemany("INSERT INTO walmart_sales VALUES (?)", [(10,), (20,)])

    class SqliteConnector:
        dialect = "sqlite"

        def run(self, sql):
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
                cursor = connection.execute(sql)
                return [cursor.description, *cursor.fetchall()]

    state = {"conv_id": "parallel-correction", "database_name": "Walmart_Sales"}
    query = make_sql_query(state, SqliteConnector(), max_calls=8)
    agent = bound_agent(state, [query])
    agent.bind(ToolPack([query]))
    agent.bind(
        AgentContext(conv_id=state["conv_id"], enable_native_function_calling=True)
    )
    columns = (
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='Walmart_Sales' ORDER BY table_name, ordinal_position"
    )
    tables = (
        "SELECT table_name, table_type FROM information_schema.tables "
        "WHERE table_schema='Walmart_Sales'"
    )
    successful_sql = "SELECT SUM(Weekly_Sales) AS total_sales FROM walmart_sales"
    object.__setattr__(
        agent,
        "_pending_native_tool_calls",
        [
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": "sql_query",
                    "arguments": json.dumps({"sql": sql}),
                },
            }
            for index, sql in enumerate(
                [columns, successful_sql if mixed_success else tables]
            )
        ],
    )
    output = await agent.act(
        AgentMessage(content="读取源数据。"),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert output.action == "sql_query, sql_query"
    assert not output.is_exe_success and output.have_retry
    assert "Correction 1 of 2" in output.content
    assert "dashboard_tool_failure" not in state
    evidence = json.loads(output.observations)
    assert evidence[0]["success"] is False
    assert "information_schema.columns" in evidence[0]["content"]
    if mixed_success:
        assert evidence[1]["success"] is True
        assert json.loads(evidence[1]["content"])["chunks"][0]["content"]["rows"] == [
            [30.0]
        ]
        assert evidence[1]["content"] in output.content
    else:
        assert evidence[1]["success"] is False
        assert "information_schema.tables" in evidence[1]["content"]
    corrected = await act(agent, "sql_query", {"sql": successful_sql})
    assert corrected.is_exe_success
    assert json.loads(corrected.content)["chunks"][0]["content"]["rows"] == [[30.0]]


@pytest.mark.parametrize(
    "fatal",
    [
        '{"error_code":"SQL_QUERY_TIMEOUT","success":false}',
        "[approval] The user rejected this sql_query call.",
        '{"error_code":"SQL_READ_ONLY_REQUIRED","success":false}',
    ],
)
def test_parallel_discovery_does_not_recover_fatal_sibling(fatal):
    invalid_sql = json.dumps(
        {
            "error_code": "SQL_QUERY_FAILED",
            "success": False,
            "chunks": [
                {"output_type": "text", "content": "no such table: information_schema"}
            ],
        }
    )
    state = {"conv_id": "fatal-sibling"}
    output = ActionOutput(
        action="sql_query, sql_query",
        is_exe_success=False,
        content=f"{invalid_sql}\n\n{fatal}",
        observations=json.dumps(
            [
                {"name": "sql_query", "success": False, "observation": invalid_sql},
                {"name": "sql_query", "success": False, "observation": fatal},
            ]
        ),
    )
    assert discovery_correction(state, output) is None
    assert "_dashboard_discovery_corrections" not in state
    failure = capture_tool_failure(state, output)
    assert failure["stage_label"] == "探索源数据"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"operations": "remove"},
        {"operations": [{"op": "replace", "path": "/widgets/by-id/value-card/title"}]},
        {"op": "replace", "path": "/widgets/by-id/value-card/title"},
    ],
)
async def test_proposal_parse_failure_never_becomes_question(
    annotation_services, arguments
):
    pack, base, events = _proposal(annotation_services)
    state = {"conv_id": "failed-annotation-turn"}

    async def capture(kind, payload):
        events.append((kind, payload))

    question = make_question(state, capture)
    agent = bound_agent(state, [*pack.sub_resources, question])
    output = await act(agent, "propose_dashboard_change", {**base, **arguments})
    assert not output.is_exe_success and not output.have_retry
    failure = generation_failure(state)
    assert failure["type"] == "dashboard.generation.failed"
    assert failure["stage_label"] == "生成批注修改提案"
    assert failure["retry_hint"] and "失败原因" in failure["message"]
    assert "operations" in failure["message"] or "top-level" in failure["message"]
    # Even a stale model response trying to ask the original English technical
    # question cannot register a request or emit question.asked after this failure.
    again = await act(
        agent,
        "question",
        {"questions": ["Why is the operations field failing to parse?"]},
    )
    assert not again.is_exe_success and not again.have_retry
    assert again.content == output.content
    with pytest.raises(RuntimeError, match="失败原因"):
        await question(questions=["Why is parsing failing?"])
    assert not any(kind == "question.asked" for kind, _ in events)
    assert (
        annotation_services[1]
        .get_dashboard("annotation-dashboard", "alice")
        .current_revision
        == 1
    )


@pytest.mark.asyncio
async def test_internal_tool_exception_stops_without_relabeling_as_question():
    @tool(description="Read stored context", args={})
    async def load_dashboard_draft():
        raise RuntimeError("Test storage connection unavailable")

    state = {"conv_id": "internal-failure"}
    agent = bound_agent(state, [load_dashboard_draft])
    output = await act(agent, "load_dashboard_draft", {})
    assert not output.is_exe_success and not output.have_retry
    assert "Test storage connection unavailable" in output.content
    assert generation_failure(state)["stage_label"] == "加载已保存看板"


@pytest.mark.asyncio
async def test_sqlite_catalog_error_gets_bounded_correction():
    @tool(description="Query sales")
    async def sql_query(sql: str):
        return json.dumps(
            {
                "success": False,
                "error_code": "SQL_QUERY_FAILED",
                "chunks": [
                    {
                        "output_type": "text",
                        "content": "SQL_QUERY_FAILED: no such table: "
                        "information_schema.columns",
                    }
                ],
            }
        )

    state = {"conv_id": "catalog-correction"}
    agent = bound_agent(state, [sql_query])
    for attempt in range(2):
        output = await act(
            agent, "sql_query", {"sql": "SELECT * FROM information_schema.columns"}
        )
        assert not output.is_exe_success and output.have_retry
        assert f"Correction {attempt + 1} of 2" in output.content
        assert "SQLite has no information_schema" in output.content
        assert "dashboard_tool_failure" not in state
    output = await act(
        agent, "sql_query", {"sql": "SELECT * FROM information_schema.columns"}
    )
    assert not output.have_retry
    assert generation_failure(state)["stage_label"] == "探索源数据"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code", ["SQL_QUERY_TIMEOUT", "SQL_READ_ONLY_REQUIRED", "ARTIFACT_CAPTURE_FAILED"]
)
async def test_sql_non_authoring_errors_still_stop(code):
    @tool(description="Query sales")
    async def sql_query(sql: str):
        return json.dumps({"success": False, "error_code": code})

    state = {"conv_id": f"sql-stop-{code}"}
    agent = bound_agent(state, [sql_query])
    output = await act(agent, "sql_query", {"sql": "SELECT * FROM walmart_sales"})
    assert not output.is_exe_success and not output.have_retry
    assert "dashboard_tool_failure" in state


@pytest.mark.asyncio
async def test_invalid_question_arguments_follow_failure_path_without_question_event():
    state, events = {"conv_id": "invalid-question"}, []

    async def capture(kind, payload):
        events.append((kind, payload))

    agent = bound_agent(state, [make_question(state, capture)])
    output = await act(agent, "question", {"questions": [None, "second"]})
    assert not output.is_exe_success and not output.have_retry
    assert generation_failure(state)["reason"] == "invalid_question_parameters"
    assert not events


@pytest.mark.asyncio
async def test_fresh_turn_business_clarification_still_binds_the_real_answer():
    state, events = {"conv_id": "fresh-business-turn"}, []

    async def capture(kind, payload):
        events.append((kind, payload))
        if kind == "question.asked":
            question_manager.reply(payload["request_id"], [["经营负责人"]])

    agent = bound_agent(state, [make_question(state, capture)])
    output = await act(agent, "question", {"questions": ["看板的主要受众是谁？"]})
    assert output.is_exe_success and "经营负责人" in output.content
    assert generation_failure(state) is None
    assert [kind for kind, _ in events] == ["question.asked", "question.replied"]
    assert events[0][1]["request_id"] == events[1][1]["request_id"]
