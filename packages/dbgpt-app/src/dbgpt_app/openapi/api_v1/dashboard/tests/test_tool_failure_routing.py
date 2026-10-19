"""Real ReAct dispatch must stop failed tools before a technical question can run."""

import json

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.resource import ToolPack
from dbgpt.agent.resource.tool.base import tool
from dbgpt_app.openapi.api_v1.dashboard.confirmation import (
    DashboardConfirmationAgent,
    generation_failure,
)
from dbgpt_app.openapi.api_v1.tools.question import make_question
from dbgpt_app.openapi.api_v1.tools.question_manager import question_manager

from .test_proposal_tool_contract import _proposal
from .test_proposal_tool_contract import (
    annotation_services as _annotation_services_fixture,
)

annotation_services = _annotation_services_fixture


def bound_agent(state, tools):
    agent = DashboardConfirmationAgent(dashboard_state=state)
    agent.bind(AgentContext(conv_id=state["conv_id"]))
    pack = ToolPack(tools)
    for action in agent.actions:
        action.init_resource(pack)
    return agent


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
