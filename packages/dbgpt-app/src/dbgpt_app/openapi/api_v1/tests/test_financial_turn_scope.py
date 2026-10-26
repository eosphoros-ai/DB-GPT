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
