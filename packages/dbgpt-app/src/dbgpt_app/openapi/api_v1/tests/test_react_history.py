"""Tests for ReAct multi-turn conversation history (#3171)."""

import json

from dbgpt.core import ModelMessageRoleType
from dbgpt.core.interface.message import AIMessage, HumanMessage, ViewMessage
from dbgpt_app.openapi.api_v1.react_history import (
    build_react_historical_dialogues,
    extract_react_final_content,
    history_prompt_hint,
)


def test_extract_prefers_final_content_from_view_payload():
    payload = json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": "order_id=3, sku_id=100",
            "steps": [{"action": "sql_query"}],
        },
        ensure_ascii=False,
    )
    assert extract_react_final_content(payload) == "order_id=3, sku_id=100"


def test_extract_keeps_plain_text_and_truncates():
    assert extract_react_final_content("hello") == "hello"
    assert extract_react_final_content("abcdef", max_chars=5) == "ab..."


def test_build_dialogues_skips_current_unanswered_turn():
    messages = [
        HumanMessage(content="查询26年单次已经消费gmv最大的订单是哪个？"),
        ViewMessage(
            content=json.dumps(
                {
                    "version": 1,
                    "type": "react-agent",
                    "final_content": "order_id=3, sku_id=100, gmv=20",
                },
                ensure_ascii=False,
            )
        ),
        HumanMessage(content="统计和上面单次消费gmv最大订单所属商品的总计gmv有多少？"),
    ]

    dialogues = build_react_historical_dialogues(
        messages,
        current_user_input="统计和上面单次消费gmv最大订单所属商品的总计gmv有多少？",
    )

    assert len(dialogues) == 2
    assert dialogues[0].role == ModelMessageRoleType.HUMAN
    assert "查询26年单次已经消费gmv最大的订单是哪个？" in dialogues[0].content
    assert dialogues[1].role == ModelMessageRoleType.AI
    assert "sku_id=100" in dialogues[1].content
    assert "上面" not in dialogues[0].content


def test_build_dialogues_keeps_last_n_turns_and_accepts_ai_role():
    messages = [
        HumanMessage(content="q1"),
        AIMessage(content="a1"),
        HumanMessage(content="q2"),
        ViewMessage(content="a2"),
        HumanMessage(content="q3"),
        ViewMessage(content="a3"),
        HumanMessage(content="now"),
    ]
    dialogues = build_react_historical_dialogues(
        messages, current_user_input="now", max_turns=2
    )
    texts = [m.content for m in dialogues]
    assert texts == [
        "Previous question: q2",
        "Previous result: a2",
        "Previous question: q3",
        "Previous result: a3",
    ]


def test_history_prompt_hint_only_when_dialogues_exist():
    assert history_prompt_hint([]) == ""
    assert "Previous conversation" in history_prompt_hint(
        build_react_historical_dialogues(
            [HumanMessage(content="q"), ViewMessage(content="a")],
            current_user_input="next",
        )
    )
