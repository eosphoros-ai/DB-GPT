import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dbgpt.agent import AgentContext, AgentMessage
from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
from dbgpt.agent.resource.tool.pack import ToolPack
from dbgpt.agent.util.react_parser import extract_terminate_output
from dbgpt_app.openapi.api_v1 import financial_agent
from dbgpt_app.openapi.api_v1.financial_agent import FinancialWorkflowAgent
from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    _result,
    finalize_financial_answer,
    financial_execution_guidance,
    make_financial_tools,
)
from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.summary import report_summary, summary_context
from dbgpt_serve.financial_analysis.tests import conftest as financial_fixtures
from dbgpt_serve.financial_analysis.tests.conftest import wait_ready
from dbgpt_serve.financial_analysis.tests.test_comparison_service import create
from dbgpt_serve.financial_analysis.tests.test_workflow_loops import (
    ready_report,
    reviews,
    topic_findings,
)

isolated_service = financial_fixtures.isolated_service


def test_semantic_repair_has_scoped_data_and_can_pass_after_chinese_section_patch():
    report = ready_report()
    report = workflow.review_report(report, reviews(report, "recurring"))
    original = deepcopy(report["findings"])
    payload = json.loads(_result(report, "scope"))["model_context"]
    repair = payload["repair"]
    assert repair["review"]["verdict"] == "revise"
    assert repair["review"]["note"] == workflow.topic(report, "recurring")["note"]
    assert repair["section"] == "profitability"
    assert repair["data"]["facts"][0]["entityId"]
    assert all(f["reference"] for f in repair["data"]["facts"])
    assert payload["next_action"] == workflow.next_action(report)
    assert json.dumps(payload["next_action"], ensure_ascii=False) in (
        financial_execution_guidance({"financial_report_context": report})
    )
    report = workflow.save_topic(
        report,
        "recurring",
        patches=[{"finding_index": 0, "changes": {"section": "盈利质量"}}],
    )
    assert workflow.topic(report, "recurring")["status"] == "ready"
    assert all(
        f in report["findings"]
        for f in original
        if f["id"] not in workflow.topic(report, "recurring")["findingIds"]
    )
    report = workflow.publish(workflow.review_report(report, reviews(report)))
    assert report["workflow"]["status"] == "published"


def live_tools_agent(service, report, *, pending=True):
    run_id = report["report"]["run"]["id"]
    state = {
        "owner_id": "alice",
        "conv_id": "scope",
        "financial_report_context": deepcopy(report),
        "financial_pending": {run_id} if pending else set(),
    }
    tools = make_financial_tools(state, service=service)
    agent = FinancialWorkflowAgent(report_repair_state=state, max_retry_count=60)
    agent.agent_context = AgentContext(conv_id="scope")
    agent.resource = ToolPack([fn._tool for fn in tools])
    agent._check_and_add_terminate()
    for action in agent.actions:
        action.init_resource(agent.resource)
    return agent, state


async def call(agent, name, **args):
    return await agent.act(
        AgentMessage(
            content=f"Action: {name}\nAction Input: "
            + json.dumps(args, ensure_ascii=False)
        ),
        agent,
        **agent.prepare_act_param(None, agent),
    )


def ready_saved_report(service):
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    for topic_id in workflow.TOPICS:
        report = service.update_agent_workflow(
            "alice", "scope", run_id, report["revision"], "start", topic_id=topic_id
        )
        report = service.update_agent_workflow(
            "alice",
            "scope",
            run_id,
            report["revision"],
            "save",
            topic_id=topic_id,
            findings=topic_findings(report, topic_id),
        )
    assert all(t["status"] == "ready" for t in report["workflow"]["topics"])
    return report


@pytest.mark.asyncio
async def test_real_tools_review_repair_review_publishes_without_reextracting(
    isolated_service,
):
    service, _, extraction_calls, _ = isolated_service
    report = ready_saved_report(service)
    run_id = report["report"]["run"]["id"]
    initial_calls = extraction_calls[:]
    agent, state = live_tools_agent(service, report)
    out = await call(
        agent,
        "review_financial_report",
        run_id=run_id,
        revision=report["revision"],
        reviews=reviews(report, "recurring"),
    )
    assert out.is_exe_success and json.loads(out.content)["model_context"]["repair"]
    current = state["financial_report_context"]
    saved_revision = current["revision"]
    out = await call(
        agent,
        "review_financial_report",
        run_id=run_id,
        revision=saved_revision,
        reviews=reviews(current),
    )
    assert not out.is_exe_success
    assert "next_action" in out.content and "save_financial_topic" in out.content
    assert (
        service.get("alice", "scope", run_id, report=True)["revision"] == saved_revision
    )
    out = await call(
        agent,
        "save_financial_topic",
        run_id=run_id,
        revision=saved_revision,
        topic_id="recurring",
        patches=[{"finding_index": 0, "changes": {"section": "盈利质量"}}],
    )
    assert out.is_exe_success and state["_financial_stalled_calls"] == 0
    current = state["financial_report_context"]
    out = await call(
        agent,
        "review_financial_report",
        run_id=run_id,
        revision=current["revision"],
        reviews=reviews(current),
    )
    assert out.is_exe_success
    assert state["financial_report_context"]["workflow"]["status"] == "published"
    assert not state["financial_pending"]
    assert extraction_calls == initial_calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,topic_id",
    [
        ("get_financial_topic", "recurring"),
        ("get_financial_topic", "operating"),
        ("read_financial_report", None),
    ],
)
@pytest.mark.parametrize("native", [False, True])
async def test_generate_reply_stops_successful_read_loop_with_real_tools(
    isolated_service,
    tool_name,
    topic_id,
    native,
):
    service, _, _, _ = isolated_service
    report = ready_saved_report(service)
    # This is the screenshot's ready/failed topic read while another topic
    # is awaiting repair. A terminal get is a successful no-op in the service.
    report = service.update_agent_workflow(
        "alice",
        "scope",
        report["report"]["run"]["id"],
        report["revision"],
        "review",
        reviews=reviews(report, "recurring"),
    )
    agent, state = live_tools_agent(service, report)
    agent.agent_context.enable_native_function_calling = native
    args = {"run_id": report["report"]["run"]["id"]}
    if topic_id:
        args["topic_id"] = topic_id

    async def repeated_read(*_args, **_kwargs):
        if native:
            object.__setattr__(
                agent,
                "_pending_native_tool_calls",
                [{"function": {"name": tool_name, "arguments": json.dumps(args)}}],
            )
            return "", "synthetic"
        return (
            f"Action: {tool_name}\nAction Input: " + json.dumps(args),
            "synthetic",
        )

    think = AsyncMock(side_effect=repeated_read)
    object.__setattr__(agent, "thinking", think)
    object.__setattr__(
        agent, "_load_thinking_messages", AsyncMock(return_value=([], None))
    )
    for method in ("send", "write_memories", "adjust_final_message"):
        object.__setattr__(agent, method, AsyncMock())
    object.__setattr__(agent, "review", AsyncMock(return_value=(True, None)))
    reply = await agent.generate_reply(
        received_message=AgentMessage(content="continue"), sender=agent
    )
    assert think.await_count == 3
    assert reply.success is False and reply.action_report.have_retry is False
    assert reply.action_report.content.startswith("FINANCIAL_NO_PROGRESS:")
    current = service.get("alice", "scope", args["run_id"], report=True)
    assert current == report and current["workflow"]["status"] == "draft"
    assert state["_financial_stalled_calls"] == 3


@pytest.mark.asyncio
async def test_agent_stops_semantic_cycle_at_persisted_budget(isolated_service):
    service, _, _, _ = isolated_service
    report = ready_saved_report(service)
    agent, state = live_tools_agent(service, report)
    run_id = report["report"]["run"]["id"]
    for _ in range(2):
        report = state["financial_report_context"]
        out = await call(
            agent,
            "review_financial_report",
            run_id=run_id,
            revision=report["revision"],
            reviews=reviews(report, "recurring"),
        )
        assert out.is_exe_success
        report = state["financial_report_context"]
        out = await call(
            agent,
            "save_financial_topic",
            run_id=run_id,
            revision=report["revision"],
            topic_id="recurring",
            patches=[{"finding_index": 0, "changes": {"section": "盈利质量"}}],
        )
        assert out.is_exe_success
    report = state["financial_report_context"]
    out = await call(
        agent,
        "review_financial_report",
        run_id=run_id,
        revision=report["revision"],
        reviews=reviews(report, "recurring"),
    )
    assert not out.is_exe_success and not out.have_retry
    assert out.content.startswith("FINANCIAL_NO_PROGRESS:")
    assert service.get("alice", "scope", run_id, report=True) == report
    assert report["workflow"]["status"] == "draft"


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ['{"file_ids":', '["a", "b"]', "{}"])
async def test_malformed_prepare_cannot_restart_active_workflow(
    isolated_service, arguments
):
    service, _, _, _ = isolated_service
    report = ready_saved_report(service)
    agent, _ = live_tools_agent(service, report)
    execute = AsyncMock()
    object.__setattr__(agent.resource, "async_execute", execute)
    out = await agent.act(
        AgentMessage(
            content="Action: prepare_financial_comparison\nAction Input: " + arguments
        ),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert not out.is_exe_success and out.have_retry
    assert "FINANCIAL_WORKFLOW_BLOCKED" in out.content
    assert json.loads(out.content)["model_context"]["next_action"]["tool"] == (
        "review_financial_report"
    )
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_thinking_requires_current_transition_and_pins_revision(
    isolated_service,
):
    from dbgpt.core import ModelOutput

    service, _, _, _ = isolated_service
    report = ready_saved_report(service)
    agent, _ = live_tools_agent(service, report)
    agent.agent_context.enable_native_function_calling = True
    create_output = AsyncMock(return_value=ModelOutput.build(""))
    object.__setattr__(
        agent, "llm_client", SimpleNamespace(create_with_output=create_output)
    )
    object.__setattr__(agent, "memory", SimpleNamespace(gpts_memory=None))
    object.__setattr__(
        agent, "_a_select_llm_model", AsyncMock(return_value="synthetic")
    )
    message = AgentMessage(role="system", content="Analyze the saved report.")
    await agent.thinking([message])
    request = create_output.call_args.kwargs
    assert request["tool_choice"] == "required"
    assert {tool["function"]["name"] for tool in request["tools"]} == {
        "review_financial_report",
        "read_financial_report",
    }
    assert report["revision"] in request["messages"][0]["content"]
    assert message.content == "Analyze the saved report."


@pytest.mark.asyncio
async def test_draft_followup_reads_and_explicit_retry_remain_available(
    isolated_service,
):
    service, _, _, _ = isolated_service
    report = ready_saved_report(service)
    agent, state = live_tools_agent(service, report, pending=False)
    run_id = report["report"]["run"]["id"]
    for _ in range(4):
        out = await call(agent, "read_financial_report", run_id=run_id)
        assert out.is_exe_success and out.have_retry
    assert not state["financial_pending"]
    out = await call(
        agent, "get_financial_topic", run_id=run_id, topic_id="operating", retry=True
    )
    assert out.is_exe_success and run_id in state["financial_pending"]
    assert workflow.topic(state["financial_report_context"], "operating")["status"] == (
        "running"
    )
    names = {t["function"]["name"] for t in agent._build_native_tools()}
    assert names == {
        "get_financial_topic",
        "save_financial_topic",
        "read_financial_report",
    }


async def published_agent(service):
    report = ready_saved_report(service)
    agent, state = live_tools_agent(service, report)
    out = await call(
        agent,
        "review_financial_report",
        run_id=report["report"]["run"]["id"],
        revision=report["revision"],
        reviews=reviews(report),
    )
    assert out.is_exe_success
    assert state["financial_report_context"]["workflow"]["status"] == "published"
    assert state["_financial_completion"]["attempts"] == 0
    return agent, state


def stub_reply_dependencies(agent):
    object.__setattr__(
        agent, "_load_thinking_messages", AsyncMock(return_value=([], None))
    )
    for method in ("send", "write_memories", "adjust_final_message"):
        object.__setattr__(agent, method, AsyncMock())
    object.__setattr__(agent, "review", AsyncMock(return_value=(True, None)))


@pytest.mark.asyncio
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("pattern", ["mixed", "invalid_answer", "malformed"])
async def test_publication_completion_bounds_alternating_errors_and_tools(
    isolated_service, native, pattern
):
    service, _, extraction_calls, _ = isolated_service
    agent, state = await published_agent(service)
    report = deepcopy(state["financial_report_context"])
    extractions = extraction_calls[:]
    agent.agent_context.enable_native_function_calling = native
    # Forbid any backend dispatch. Even a well-formed prepare/read must never
    # run after publication; their previous successes reset the protocol budget.
    execute = AsyncMock(side_effect=AssertionError("unexpected financial tool"))
    object.__setattr__(agent.resource, "async_execute", execute)
    attempts = []

    async def model_response(*_args, **_kwargs):
        attempt = len(attempts)
        attempts.append(attempt)
        if pattern == "mixed":
            name = [None, "prepare_financial_report", "read_financial_report"][attempt]
            args = {"run_id": report["report"]["run"]["id"]}
        elif pattern == "invalid_answer":
            name, args = "terminate", {"output": "偿债能力很强，足以覆盖所有风险。"}
        else:
            name, args = "terminate", '{"output":'
        object.__setattr__(agent, "_pending_native_tool_calls", None)
        if not name:
            return "财报已经完成，下面直接回答。", "synthetic"
        arguments = args if isinstance(args, str) else json.dumps(args)
        if native:
            object.__setattr__(
                agent,
                "_pending_native_tool_calls",
                [{"function": {"name": name, "arguments": arguments}}],
            )
            return "", "synthetic"
        return f"Action: {name}\nAction Input: {arguments}", "synthetic"

    think = AsyncMock(side_effect=model_response)
    object.__setattr__(agent, "thinking", think)
    stub_reply_dependencies(agent)
    reply = await agent.generate_reply(
        received_message=AgentMessage(content="finish"), sender=agent
    )
    assert think.await_count == 3
    assert reply.success and reply.action_report.terminate
    assert reply.action_report.have_retry is False
    answer = extract_terminate_output(reply.action_report.content)
    assert answer == report_summary(report)
    assert finalize_financial_answer(answer, state) == answer
    assert state["_financial_completion"]["attempts"] == 3
    assert state["_financial_completion"]["fallback_reason"] == "completion_budget"
    execute.assert_not_awaited()
    assert extraction_calls == extractions
    assert (
        service.get("alice", "scope", report["report"]["run"]["id"], report=True)
        == report
    )


@pytest.mark.asyncio
async def test_completion_native_prompt_only_supplies_required_terminate(
    isolated_service,
):
    from dbgpt.core import ModelOutput

    service, _, _, _ = isolated_service
    agent, state = await published_agent(service)
    agent.agent_context.enable_native_function_calling = True
    create_output = AsyncMock(return_value=ModelOutput.build(""))
    object.__setattr__(
        agent, "llm_client", SimpleNamespace(create_with_output=create_output)
    )
    object.__setattr__(agent, "memory", SimpleNamespace(gpts_memory=None))
    object.__setattr__(
        agent, "_a_select_llm_model", AsyncMock(return_value="synthetic")
    )
    original = AgentMessage(role="system", content="Finish analysis.")
    await agent.thinking([original])
    request = create_output.call_args.kwargs
    assert request["tool_choice"] == "required"
    assert {tool["function"]["name"] for tool in request["tools"]} == {"terminate"}
    assert "现在只调用 terminate" in request["messages"][0]["content"]
    assert original.content == "Finish analysis."
    assert state["_financial_completion"]["attempts"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_first", [False, True])
async def test_valid_completion_keeps_model_answer_and_citations(
    isolated_service, repair_first
):
    service, _, _, _ = isolated_service
    agent, state = await published_agent(service)
    report = state["financial_report_context"]
    if repair_first:
        rejected = await call(agent, "terminate", output="偿债能力很强。")
        valid, error = await agent.verify(AgentMessage(action_report=rejected), agent)
        assert not valid and "只修正 terminate" in error
        assert state["financial_answer_repairs"] == 1
    fact = summary_context(report)["facts"][0]
    answer = fact["metricName"] + "为" + fact["reference"] + "。"
    out = await call(agent, "terminate", output=answer)
    message = AgentMessage(action_report=out)
    assert await agent.verify(message, agent) == (True, None)
    assert extract_terminate_output(out.content) == answer
    rendered = finalize_financial_answer(answer, state)
    assert "#financial-report/" in rendered
    assert "fallback_reason" not in state["_financial_completion"]
    assert state["_financial_completion"]["attempts"] == (2 if repair_first else 1)


@pytest.mark.asyncio
async def test_completion_deadline_cancels_model_and_finishes_saved_report(
    isolated_service, monkeypatch
):
    service, _, _, _ = isolated_service
    agent, state = await published_agent(service)
    cancelled = asyncio.Event()

    async def slow_model(*_args, **_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(ToolCallingReActAgent, "thinking", slow_model)
    object.__setattr__(agent, "_completion_remaining", lambda phase: 0.02)
    stub_reply_dependencies(agent)
    reply = await asyncio.wait_for(
        agent.generate_reply(
            received_message=AgentMessage(content="finish"), sender=agent
        ),
        timeout=5,
    )
    assert cancelled.is_set()
    assert reply.success and reply.action_report.terminate
    assert extract_terminate_output(reply.action_report.content) == report_summary(
        state["financial_report_context"]
    )
    assert state["_financial_completion"]["attempts"] == 1
    assert state["_financial_completion"]["fallback_reason"] == "TimeoutError"


@pytest.mark.asyncio
async def test_completion_deadline_is_cumulative_and_never_starts_another_model(
    isolated_service, monkeypatch
):
    service, _, _, _ = isolated_service
    agent, state = await published_agent(service)
    phase = state["_financial_completion"]
    started = phase["started"]
    await agent.act(AgentMessage(content="plain reply"), agent)
    assert phase["started"] == started and phase["attempts"] == 1
    phase["started"] -= financial_agent.FINANCIAL_COMPLETION_TIMEOUT + 1
    think = AsyncMock()
    monkeypatch.setattr(ToolCallingReActAgent, "thinking", think)
    stub_reply_dependencies(agent)
    reply = await agent.generate_reply(
        received_message=AgentMessage(content="finish"), sender=agent
    )
    think.assert_not_awaited()
    assert reply.success and reply.action_report.terminate


@pytest.mark.asyncio
async def test_cancelling_completion_preserves_user_stop(isolated_service, monkeypatch):
    service, _, _, _ = isolated_service
    agent, state = await published_agent(service)
    thinking = AsyncMock(side_effect=asyncio.CancelledError())
    monkeypatch.setattr(ToolCallingReActAgent, "thinking", thinking)
    with pytest.raises(asyncio.CancelledError):
        await agent.thinking([])
    assert "fallback_output" not in state["_financial_completion"]
    assert state["financial_report_context"]["workflow"]["status"] == "published"


@pytest.mark.asyncio
async def test_completion_rejects_entire_batch_before_any_tool_runs(isolated_service):
    service, _, _, _ = isolated_service
    agent, state = await published_agent(service)
    execute = AsyncMock(side_effect=AssertionError("unexpected financial tool"))
    object.__setattr__(agent.resource, "async_execute", execute)
    out = await agent.act(
        AgentMessage(content=""),
        agent,
        tool_calls=[
            {"function": {"name": "terminate", "arguments": '{"output":"done"}'}},
            {"function": {"name": "prepare_financial_report", "arguments": "{}"}},
        ],
    )
    assert not out.is_exe_success and "FINANCIAL_COMPLETION_ONLY" in out.content
    assert state["_financial_completion"]["attempts"] == 1
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_turn_can_read_published_report_and_explicitly_revise(
    isolated_service,
):
    service, _, _, _ = isolated_service
    _, previous = await published_agent(service)
    report = previous["financial_report_context"]
    agent, state = live_tools_agent(service, report, pending=False)
    run_id = report["report"]["run"]["id"]
    assert "read_financial_report" in {
        t["function"]["name"] for t in agent._build_native_tools()
    }
    out = await call(agent, "read_financial_report", run_id=run_id)
    assert out.is_exe_success and state["financial_read"]
    assert agent._completion_phase() is None
    out = await call(
        agent, "get_financial_topic", run_id=run_id, topic_id="operating", retry=True
    )
    assert out.is_exe_success
    assert state["financial_report_context"]["workflow"]["status"] == "draft"
    assert agent._completion_phase() is None
