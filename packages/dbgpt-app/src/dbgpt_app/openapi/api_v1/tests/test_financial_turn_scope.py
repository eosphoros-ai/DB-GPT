from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    finalize_financial_answer,
    financial_answer_error,
    financial_completion_error,
    is_financial_turn,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    ["你好", "今天上海天气怎么样", "写一个 Python 排序函数", "Explain photosynthesis"],
)
async def test_unrelated_turn_never_requires_report_read_or_rewrites_answer(question):
    state = {
        "financial_user_query": question,
        "owner_id": "alice",
        "conv_id": "scope",
    }
    backend = SimpleNamespace(latest_agent_report=Mock())
    assert await financial_completion_error(state, service=backend) is None
    backend.latest_agent_report.assert_not_called()
    # Even an unnecessary model-initiated read must not hijack the answer.
    state.update(financial_report_context={"revision": "saved"}, financial_read=True)
    assert financial_answer_error("A normal answer.", state) is None
    assert finalize_financial_answer("A normal answer.", state) == "A normal answer."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "营业收入为什么下降",
        "现金流有什么风险",
        "这家公司怎么样",
        "这份报告还有什么值得关注",
        "为什么",
        "详细说说",
        "What was its profit margin?",
        "Tell me more",
    ],
)
async def test_financial_followup_requires_fresh_read_even_without_tool_call(question):
    state = {
        "financial_user_query": question,
        "owner_id": "alice",
        "conv_id": "scope",
    }
    backend = SimpleNamespace(latest_agent_report=Mock(return_value={"revision": "v1"}))
    assert "read_financial_report" in await financial_completion_error(
        state, service=backend
    )
    backend.latest_agent_report.assert_called_once_with("alice", "scope")
    state.update(financial_report_context={"revision": "v1"}, financial_read=True)
    assert "数据不足" in finalize_financial_answer("Unreferenced numbers: 42", state)


def test_active_analysis_keeps_publication_gate():
    assert is_financial_turn(
        {"financial_user_query": "你好", "financial_pending": {"active-run"}}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_key", ["financial_other_source_selected", "financial_other_source_used"]
)
async def test_other_data_source_keeps_its_answer_after_an_unnecessary_report_read(
    source_key,
):
    state = {
        "financial_user_query": "按地区汇总营业收入",
        "owner_id": "alice",
        "conv_id": "scope",
        source_key: True,
    }
    backend = SimpleNamespace(latest_agent_report=Mock(return_value={"revision": "v1"}))
    assert await financial_completion_error(state, service=backend) is None
    backend.latest_agent_report.assert_not_called()
    state.update(financial_report_context={"revision": "v1"}, financial_read=True)
    answer = "数据库结果：华东地区营业收入为 42 万元。"
    assert financial_answer_error(answer, state) is None
    assert finalize_financial_answer(answer, state) == answer
    state["financial_pending"] = {"active-run"}
    assert "publish_financial_report" in await financial_completion_error(
        state, service=backend
    )


@pytest.mark.asyncio
async def test_financial_keyword_without_registered_service_can_complete(monkeypatch):
    from dbgpt._private.config import Config
    from dbgpt.component import SystemApp

    monkeypatch.setattr(Config(), "SYSTEM_APP", SystemApp())
    state = {
        "financial_user_query": "解释利润",
        "owner_id": "alice",
        "conv_id": "scope",
    }
    assert await financial_completion_error(state) is None


def test_report_followup_retains_an_honest_qualitative_answer():
    state = {
        "financial_user_query": "这份报告有什么限制",
        "financial_report_context": {"revision": "saved"},
        "financial_read": True,
    }
    answer = "现有摘录不足以解释变化原因，需要核对附注。"
    assert finalize_financial_answer(answer, state) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize("native", [False, True])
async def test_executed_sql_keeps_financial_keywords_outside_report_gate(native):
    from dbgpt.agent import AgentContext, AgentMessage
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.financial_agent import FinancialWorkflowAgent
    from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query

    state = {
        "financial_user_query": "按地区汇总营业收入",
        "owner_id": "alice",
        "conv_id": "scope",
    }
    connector = SimpleNamespace(
        dialect="sqlite", run=lambda sql: [("region", "revenue"), ("East", 42)]
    )
    sql = make_sql_query(state, connector)
    agent = FinancialWorkflowAgent(report_repair_state=state)
    agent.agent_context = AgentContext(
        conv_id="scope", enable_native_function_calling=native
    )
    agent.resource = ToolPack([sql._tool])
    agent._check_and_add_terminate()
    for action in agent.actions:
        action.init_resource(agent.resource)
    arguments = '{"sql":"SELECT region, SUM(revenue) FROM sales GROUP BY region"}'
    if native:
        object.__setattr__(
            agent,
            "_pending_native_tool_calls",
            [
                {
                    "id": "query",
                    "type": "function",
                    "function": {"name": "sql_query", "arguments": arguments},
                }
            ],
        )
    result = await agent.act(
        AgentMessage(content="Action: sql_query\nAction Input: " + arguments),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert result.is_exe_success and "42" in result.content
    backend = SimpleNamespace(
        latest_agent_report=Mock(return_value={"revision": "old"})
    )
    assert await financial_completion_error(state, service=backend) is None
    backend.latest_agent_report.assert_not_called()
    answer = "East revenue: 42"
    assert finalize_financial_answer(answer, state) == answer
