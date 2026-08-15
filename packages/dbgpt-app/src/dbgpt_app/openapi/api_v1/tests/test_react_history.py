"""Tests for ReAct multi-turn conversation history (#3171)."""

import json

from dbgpt.core.interface.message import AIMessage, HumanMessage, ViewMessage
from dbgpt_app.openapi.api_v1.react_history import (
    completed_turn_pairs,
    extract_react_final_content,
    format_react_followup_question,
    history_prompt_hint,
)

# Issue #3171 reproduction: turn 2 refers to "上面" the max-GMV consumed order.
TURN1_Q = "查询26年单次已经消费gmv最大的订单是哪个？"
TURN1_A = "order_id=3, sku_id=100, gmv=20（consume_status=1）"
TURN2_Q = "统计和上面单次消费gmv最大订单所属商品的总计gmv有多少？"


def _turn1_view_payload(final_content: str = TURN1_A) -> str:
    return json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": final_content,
            "steps": [
                {"action": "sql_query", "action_input": '{"sql": "SELECT ..."}'},
            ],
        },
        ensure_ascii=False,
    )


def _issue_3171_messages():
    return [
        HumanMessage(content=TURN1_Q),
        ViewMessage(content=_turn1_view_payload()),
        HumanMessage(content=TURN2_Q),
    ]


def test_extract_prefers_final_content_and_drops_tool_steps():
    payload = _turn1_view_payload("order_id=3, sku_id=100")
    assert extract_react_final_content(payload) == "order_id=3, sku_id=100"
    assert "sql_query" not in extract_react_final_content(payload)


def test_extract_keeps_plain_text_and_truncates():
    assert extract_react_final_content("hello") == "hello"
    assert extract_react_final_content("abcdef", max_chars=5) == "ab..."
    assert len(extract_react_final_content("abcdef", max_chars=1)) <= 1
    assert len(extract_react_final_content("abcdef", max_chars=2)) <= 2
    assert extract_react_final_content("abcdef", max_chars=1) == "a"
    assert extract_react_final_content("abcdef", max_chars=2) == "ab"


def test_empty_final_content_does_not_inject_tool_steps():
    payload = json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": "",
            "steps": [{"action": "sql_query", "action_input": '{"sql": "SELECT 1"}'}],
        },
        ensure_ascii=False,
    )
    assert extract_react_final_content(payload) == ""
    messages = [
        HumanMessage(content="q1"),
        ViewMessage(content=payload),
        HumanMessage(content="q2"),
    ]
    assert format_react_followup_question("q2", messages) == "q2"
    assert completed_turn_pairs(messages, "q2") == []


def test_issue_3171_followup_observation_contains_sku_and_current_question():
    """What the ReAct LLM actually attends to is the last Human Observation."""
    followup = format_react_followup_question(TURN2_Q, _issue_3171_messages())
    observation = f"Observation: {followup}"

    assert "sku_id=100" in observation
    assert "order_id=3" in observation
    assert TURN1_Q in observation
    assert TURN2_Q in observation
    assert observation.strip().endswith(TURN2_Q)
    # Tool traces from turn 1 must not flood the follow-up.
    assert "sql_query" not in observation
    # First-turn current question is labeled so the agent does not re-solve it.
    assert "## Current question" in observation
    assert history_prompt_hint(True)
    assert history_prompt_hint(False) == ""


def test_first_turn_is_unchanged():
    assert format_react_followup_question("hello", [HumanMessage(content="hello")]) == (
        "hello"
    )


def test_storage_conversation_matches_react_stream_order():
    """Mirror _react_agent_stream: persist turn 1, then append turn 2 user input."""
    from dbgpt.core.interface.message import StorageConversation

    conv = StorageConversation(conv_uid="issue-3171", chat_mode="chat_react_agent")
    conv.start_new_round()
    conv.add_user_message(TURN1_Q)
    conv.add_view_message(_turn1_view_payload())
    conv.end_current_round()
    conv.start_new_round()
    conv.add_user_message(TURN2_Q)

    followup = format_react_followup_question(TURN2_Q, conv.messages)
    assert followup != TURN2_Q
    assert "sku_id=100" in followup
    assert followup.endswith(TURN2_Q)


def test_completed_pairs_keep_last_n_turns_and_accept_ai_role():
    messages = [
        HumanMessage(content="q1"),
        AIMessage(content="a1"),
        HumanMessage(content="q2"),
        ViewMessage(content="a2"),
        HumanMessage(content="q3"),
        ViewMessage(content="a3"),
        HumanMessage(content="now"),
    ]
    assert completed_turn_pairs(messages, "now", max_turns=2) == [
        ("q2", "a2"),
        ("q3", "a3"),
    ]
