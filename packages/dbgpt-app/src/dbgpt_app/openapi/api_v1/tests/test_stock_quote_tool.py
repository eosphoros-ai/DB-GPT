"""Tests for the ReAct stock quote tool, snapshot merging, and loop protection."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    defer_financial_answer,
    financial_command_input_error,
    financial_completion_error,
)
from dbgpt_app.openapi.api_v1.tools.stock_quotes import (
    make_stock_quote_tool,
    previous_quote_snapshot,
)
from dbgpt_serve.financial_analysis.quotes import DailyReports, query_quotes
from dbgpt_serve.financial_analysis.tests.test_quotes import (
    NOW,
    endpoint,
)


async def _mock_query(stocks, **kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        return await query_quotes(
            stocks, client=client, now=NOW, reports=DailyReports(), **kwargs
        )


@pytest.mark.asyncio
async def test_normalized_names_and_broad_market_work_without_literal_substring():
    # User says "茅台", agent normalizes to "贵州茅台" -> must succeed on first try!
    state = {"financial_user_query": "今天茅台涨了多少？"}
    tool = make_stock_quote_tool(state, query=_mock_query)
    out = json.loads(await tool(["贵州茅台"]))
    assert "600519.SH" in out["chunks"][0]["content"]
    assert not out["model_context"]["stop_retrying"]

    # User asks about "大盘" -> expands cleanly to CN core indices.
    market_state = {"financial_user_query": "今天大盘是跌了还是涨了？"}
    market_tool = make_stock_quote_tool(market_state, query=_mock_query)
    market_out = json.loads(await market_tool(["大盘"]))
    content = market_out["chunks"][0]["content"]
    assert "上证指数" in content and "深证成指" in content and "创业板指" in content

    # Broad market + overlapping explicit indices must deduplicate without
    # corrupting requested labels.
    overlap_state = {"financial_user_query": "今天大盘走势如何？"}
    overlap_tool = make_stock_quote_tool(overlap_state, query=_mock_query)
    await overlap_tool(["大盘", "上证指数", "深证成指"])
    overlap_rows = overlap_state["stock_quote_snapshot"]["rows"]
    assert [(r["requested"], r["quote"]["listing"]["code"]) for r in overlap_rows] == [
        ("上证指数", "000001"),
        ("深证成指", "399001"),
        ("创业板指", "399006"),
    ]

    # Follow-up mixing a previously queried stock and broad market preserves alias.
    recalled_state = {"financial_user_query": "看看贵州茅台和大盘"}
    recalled_tool = make_stock_quote_tool(
        recalled_state,
        history=[
            SimpleNamespace(
                type="view",
                content=json.dumps(
                    {"stock_quote_snapshot": state["stock_quote_snapshot"]}
                ),
            )
        ],
        query=_mock_query,
    )
    await recalled_tool(["贵州茅台", "大盘"])
    recalled_rows = recalled_state["stock_quote_snapshot"]["rows"]
    assert [r["requested"] for r in recalled_rows] == [
        "贵州茅台",
        "上证指数",
        "深证成指",
        "创业板指",
    ]


@pytest.mark.asyncio
async def test_select_merges_resolved_candidate_preserving_other_turn_stocks():
    # Default prompt: ["科技股", "贵州茅台"] -> 科技股 needs selection, 贵州茅台 quoted.
    state = {"financial_user_query": "帮我查查今天科技股和贵州茅台涨了多少？"}
    tool = make_stock_quote_tool(state, query=_mock_query)
    first = json.loads(await tool(["科技股", "贵州茅台"]))
    assert first["model_context"]["needs_selection"] is True
    assert first["model_context"]["card_rendered"] is False
    assert "question" in first["model_context"]["instructions"]
    assert state["_stock_quote_needs_question"] is True

    # Calling select before any user reply must NOT raise (prevents retry loops).
    premature = json.loads(await tool(["半导体"], "select"))
    assert premature["model_context"]["needs_selection"] is True
    assert premature["model_context"]["stop_retrying"] is True

    # Picking 半导体 via question tool merges in-place and clears pending flag.
    state["user_clarifications"] = ["半导体（BK1036）(Recommended)"]
    selected = json.loads(await tool(["半导体"], "select"))
    assert "BK1036" in selected["chunks"][0]["content"]
    assert state["_stock_quote_needs_question"] is False
    assert selected["model_context"]["card_rendered"] is True
    rows = state["stock_quote_snapshot"]["rows"]
    assert len(rows) == 2
    assert rows[0]["sector"]["code"] == "BK1036"
    assert rows[1]["quote"]["listing"]["code"] == "600519"
    assert rows[1]["quote"]["listing"]["market"] == "sh"

    # Follow-up turn recalling 贵州茅台 turnover must find the preserved row,
    # even with shorthand alias "茅台", and emit a compact card keeping all rows!
    history = [
        SimpleNamespace(
            type="view",
            content=json.dumps({"stock_quote_snapshot": state["stock_quote_snapshot"]}),
        )
    ]
    offline = AsyncMock()
    followup_state = {"financial_user_query": "刚才茅台的成交额呢？"}
    followup = make_stock_quote_tool(followup_state, history=history, query=offline)
    recalled = json.loads(await followup(["茅台"], "recall", "turnover"))
    assert "82.24 亿元人民币" in recalled["chunks"][0]["content"]
    assert recalled["model_context"]["card_rendered"] is True
    compact = followup_state["stock_quote_snapshot"]
    assert compact["display_mode"] == "compact"
    assert compact["recall_detail"] == "turnover"
    assert compact["recall_indices"] == [1]
    assert len(compact["rows"]) == 2
    offline.assert_not_awaited()

    # Subsequent recall from the compact snapshot still sees 半导体.
    next_history = [
        SimpleNamespace(
            type="view",
            content=json.dumps({"stock_quote_snapshot": compact}),
        )
    ]
    next_state = {"financial_user_query": "刚才半导体谁领涨？"}
    next_tool = make_stock_quote_tool(next_state, history=next_history, query=offline)
    gainers = json.loads(await next_tool(["半导体"], "recall", "gainers"))
    assert "宇特光电" in gainers["chunks"][0]["content"]
    assert next_state["stock_quote_snapshot"]["recall_indices"] == [0]
    offline.assert_not_awaited()


@pytest.mark.asyncio
async def test_select_natural_language_multipick_and_failed_query_preserves_snapshot():
    # Round 1: 科技股 (choose) + 贵州茅台 (quoted)
    state1 = {"financial_user_query": "查科技股和贵州茅台"}
    tool1 = make_stock_quote_tool(state1, query=_mock_query)
    await tool1(["科技股", "贵州茅台"])
    snap1 = state1["stock_quote_snapshot"]
    history1 = [
        SimpleNamespace(
            type="view",
            content=json.dumps({"stock_quote_snapshot": snap1}),
        )
    ]

    # Round 2: Natural-language reply where LLM maps to sector code BK1036 & BK0737.
    state2 = {
        "financial_user_query": "[Database: sales] 帮我看看前两个，顺便分析下前景"
    }
    tool2 = make_stock_quote_tool(state2, history=history1, query=_mock_query)
    sel = json.loads(await tool2(["BK1036", "BK0737"], "select"))
    assert sel["model_context"]["card_rendered"] is True
    merged_rows = state2["stock_quote_snapshot"]["rows"]
    # Both picked sectors are spliced in (no overwrite) and 贵州茅台 is preserved.
    assert [
        r["sector"]["code"] if r.get("sector") else r["quote"]["listing"]["code"]
        for r in merged_rows
    ] == ["BK1036", "BK0737", "600519"]

    # Round 3: All-unavailable query must NOT emit snapshot or overwrite prior snapshot.
    snap2 = state2["stock_quote_snapshot"]
    history2 = [
        SimpleNamespace(
            type="view",
            content=json.dumps({"stock_quote_snapshot": snap2}),
        )
    ]
    state3 = {"financial_user_query": "今天美股苹果涨了多少？"}
    tool3 = make_stock_quote_tool(state3, history=history2, query=_mock_query)
    bad = json.loads(await tool3(["美股苹果"]))
    assert bad["model_context"]["card_rendered"] is False
    assert "stock_quote_snapshot" not in state3

    # Also verify previous_quote_snapshot skips legacy all-unavailable snapshots.
    legacy_bad_history = [
        *history2,
        SimpleNamespace(
            type="view",
            content=json.dumps(
                {
                    "stock_quote_snapshot": {
                        "version": 1,
                        "queried_at": NOW.isoformat(),
                        "rows": [
                            {
                                "requested": "美股苹果",
                                "outcome": "unavailable",
                                "reason": "unsupported",
                            }
                        ],
                    }
                }
            ),
        ),
    ]
    restored = previous_quote_snapshot(legacy_bad_history)
    assert restored is not None and len(restored.rows) == 3


@pytest.mark.asyncio
async def test_consecutive_unavailable_queries_trigger_loop_breaker():
    state = {"financial_user_query": "今天全市场什么股票跌了？"}
    calls = []

    async def empty_query(terms, **kwargs):
        calls.append(list(terms))
        return await _mock_query(terms, **kwargs)

    tool = make_stock_quote_tool(state, query=empty_query)
    r1 = json.loads(await tool(["全市场跌幅榜"]))
    assert not r1["model_context"]["stop_retrying"]
    # Repeating the exact same failed query immediately stops retrying without network.
    r_dup = json.loads(await tool(["全市场跌幅榜"]))
    assert r_dup["model_context"]["stop_retrying"] is True
    assert len(calls) == 1
    # A second distinct unavailable query hits the breaker.
    r2 = json.loads(await tool(["不存在的冷门主题"]))
    assert r2["model_context"]["stop_retrying"] is True
    assert len(calls) == 2
    # Subsequent calls short-circuit locally without external requests.
    r3 = json.loads(await tool(["第三个不存在的词"]))
    assert r3["model_context"]["stop_retrying"] is True
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_recall_legacy_history_and_financial_safeguards():
    snap = await _mock_query(["腾讯", "贵州茅台"])
    saved = snap.model_dump(mode="json")
    history = [
        SimpleNamespace(
            type="view",
            content=json.dumps(
                {
                    "suite_binding": {"command": "/查股票"},
                    "stock_quote_snapshot": saved,
                }
            ),
        )
    ]
    remote = AsyncMock(side_effect=_mock_query)
    state = {"financial_user_query": "刚才腾讯的成交额呢"}
    tool = make_stock_quote_tool(state, history=history, query=remote)
    recalled = await tool(["腾讯"], "recall", "turnover")
    assert "102.61 亿港元" in recalled and "贵州茅台" not in recalled
    remote.assert_not_awaited()

    assert financial_command_input_error("/查股票", has_files=False) is None
    assert financial_command_input_error("/读年报", has_files=False)
    assert not defer_financial_answer(state)
    assert await financial_completion_error(state, service=object()) is None

    # Legacy /查股票 turn without saved snapshot hides older snapshots.
    legacy = [
        SimpleNamespace(
            type="view",
            content={"suite_binding": {"command": "/查股票"}, "final_content": "old"},
        )
    ]
    assert previous_quote_snapshot(legacy) is None
    legacy_tool = make_stock_quote_tool({}, history=legacy, query=remote)
    assert "未保存" in await legacy_tool([], "recall", "turnover")


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.asyncio
async def test_agent_controls_quote_lookup_and_final_answer(native):
    from dbgpt.agent import AgentContext, AgentMessage
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.agentic_data_api import _build_react_history_payload
    from dbgpt_app.openapi.api_v1.financial_agent import FinancialWorkflowAgent

    state = {"financial_user_query": "先查腾讯和贵州茅台的涨跌，再解释这能说明什么。"}
    remote = AsyncMock(side_effect=_mock_query)
    agent = FinancialWorkflowAgent(report_repair_state=state)
    agent.agent_context = AgentContext(
        conv_id="quotes", enable_native_function_calling=native
    )
    agent.resource = ToolPack([make_stock_quote_tool(state, query=remote)])
    agent._check_and_add_terminate()
    for action in agent.actions:
        action.init_resource(agent.resource)

    async def act(name, args):
        arguments = json.dumps(args, ensure_ascii=False)
        if native:
            object.__setattr__(
                agent,
                "_pending_native_tool_calls",
                [
                    {
                        "id": name,
                        "type": "function",
                        "function": {"name": name, "arguments": arguments},
                    }
                ],
            )
        msg = AgentMessage(content=f"Action: {name}\nAction Input: {arguments}")
        return await agent.act(msg, agent, **agent.prepare_act_param(None, agent))

    result = await act("query_stock_quotes", {"stocks": ["腾讯", "贵州茅台"]})
    assert result.is_exe_success and not result.terminate
    assert "00700.HK" in result.content and "600519.SH" in result.content
    final = await act("terminate", {"output": "单日价格变动无法单独验证长期需求。"})
    assert final.is_exe_success and final.terminate
    payload = _build_react_history_payload(
        final_content="单日价格变动无法单独验证长期需求。",
        steps=[],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=[],
        stock_quote_snapshot=state["stock_quote_snapshot"],
    )
    assert (
        previous_quote_snapshot([SimpleNamespace(type="view", content=payload)])
        is not None
    )


@pytest.mark.asyncio
async def test_plain_text_after_stock_quote_terminates_without_retry_round():
    from dbgpt.agent import AgentContext, AgentMessage
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt.agent.util.react_parser import extract_terminate_output
    from dbgpt_app.openapi.api_v1.financial_agent import FinancialWorkflowAgent

    state = {"financial_user_query": "今天贵州茅台涨了多少？"}
    agent = FinancialWorkflowAgent(report_repair_state=state)
    agent.agent_context = AgentContext(
        conv_id="quotes-plain", enable_native_function_calling=True
    )
    agent.resource = ToolPack([make_stock_quote_tool(state, query=_mock_query)])
    agent._check_and_add_terminate()
    for action in agent.actions:
        action.init_resource(agent.resource)

    # Before query_stock_quotes runs, plain text narration must NOT terminate early.
    pre_tool = await agent.act(
        AgentMessage(content="我先为您查询贵州茅台的今日行情。"),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert not pre_tool.is_exe_success and not pre_tool.terminate

    # Run query_stock_quotes natively.
    object.__setattr__(
        agent,
        "_pending_native_tool_calls",
        [
            {
                "id": "call-quote",
                "type": "function",
                "function": {
                    "name": "query_stock_quotes",
                    "arguments": '{"stocks":["贵州茅台"]}',
                },
            }
        ],
    )
    quoted = await agent.act(
        AgentMessage(content=""),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert quoted.is_exe_success and state.get("_stock_quote_tool_ran") is True

    # Malformed ReAct protocol text is still rejected after tool run.
    object.__setattr__(agent, "_pending_native_tool_calls", None)
    malformed = await agent.act(
        AgentMessage(content="Action: query_stock_quotes\nAction Input: {bad"),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert not malformed.is_exe_success and not malformed.terminate

    # Clean plain-text final answer after stock quote terminates directly.
    answer = "贵州茅台（600519.SH）最新价 1485.75 元，上涨 1.76%。"
    direct_final = await agent.act(
        AgentMessage(content=answer),
        agent,
        **agent.prepare_act_param(None, agent),
    )
    assert direct_final.is_exe_success and direct_final.terminate
    assert direct_final.action == "terminate"
    assert extract_terminate_output(direct_final.content) == answer
