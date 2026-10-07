"""Real historical question payloads, ordered answers and request isolation."""

import json
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1 import agentic_data_api
from dbgpt_app.openapi.api_v1.tools.question import make_question
from dbgpt_app.openapi.api_v1.tools.question_manager import QuestionManager


def _historical_questions(case):
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / f"question-case-{case}.json").read_text(
            encoding="utf-8"
        )
    )

    def walk(value):
        if isinstance(value, dict):
            if value.get("type") == "question.asked":
                yield value["questions"]
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    return next(walk(payload))


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["04", "07"])
async def test_real_historical_question_payload_and_answer_binding(monkeypatch, case):
    manager = QuestionManager()
    monkeypatch.setattr(
        "dbgpt_app.openapi.api_v1.tools.question.question_manager", manager
    )
    events = []

    async def capture(kind, payload):
        events.append((kind, payload))
        if kind == "question.asked":
            manager.reply(payload["request_id"], [["保留可计算指标"]])

    raw = _historical_questions(case)
    assert isinstance(raw[0], str) if case == "04" else isinstance(raw[0], dict)
    result = json.loads(
        await make_question({"conv_id": "question-regression"}, capture)(questions=raw)
    )
    question = events[0][1]["questions"][0]
    assert question["options"] == []
    assert question["header"] == ""
    assert question["custom"] is True
    assert question["multiple"] is False
    assert (
        f'"{question["question"]}"="保留可计算指标"' in result["chunks"][0]["content"]
    )
    assert [event[0] for event in events] == ["question.asked", "question.replied"]
    assert events[0][1]["request_id"] == events[1][1]["request_id"]
    assert events[0][1]["sequence"] == events[1][1]["sequence"]
    assert manager.list_pending() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "questions",
    [
        [],
        [{}],
        [None, "Valid second"],
        [" "],
        [{"question": "Q", "options": [{}]}],
        [{"question": "Q", "custom": False}],
    ],
)
async def test_invalid_items_reject_entire_request_instead_of_filtering(questions):
    async def unexpected_event(*_):
        raise AssertionError("Invalid question must not reach the frontend")

    result = json.loads(await make_question({}, unexpected_event)(questions=questions))
    assert "invalid questions JSON" in result["chunks"][0]["content"]


def test_out_of_order_answers_belong_to_their_exact_request_and_slot():
    manager = QuestionManager()
    first = manager.create(
        "conversation", [{"question": "A1"}, {"question": "A2"}], request_id="A"
    )
    second = manager.create("conversation", [{"question": "B1"}], request_id="B")
    assert first.sequence < second.sequence
    manager.reply("B", [["answer B1"]])
    manager.reply("A", [["answer A1"], ["answer A2"]])
    assert first.answers == [["answer A1"], ["answer A2"]]
    assert second.answers == [["answer B1"]]
    with pytest.raises(ValueError, match="already been resolved"):
        manager.reply("A", [["late overwrite"], ["late overwrite"]])
    with pytest.raises(ValueError, match="already been resolved"):
        manager.reject("A")
    assert first.answers == [["answer A1"], ["answer A2"]]
    assert second.answers == [["answer B1"]]


def test_legacy_filtered_slots_must_not_shift_the_answer():
    manager = QuestionManager()
    pending = manager.create(
        "conversation",
        [None, {"question": "second"}, {}, {"question": "fourth"}],
        request_id="A",
    )
    with pytest.raises(ValueError, match="original question index"):
        manager.reply("A", [["for second"], ["for fourth"]])
    assert pending.answers is None
    assert not pending.event.is_set()
    manager.reply("A", [[], ["for second"], [], ["for fourth"]])
    assert pending.answers[1] == ["for second"]
    assert pending.answers[3] == ["for fourth"]


def test_request_and_answer_arrays_are_not_mutated_by_later_callers():
    manager = QuestionManager()
    questions = [{"question": "original"}]
    pending = manager.create("conversation", questions, request_id="A")
    questions[0]["question"] = "changed"
    with pytest.raises(ValueError, match="already exists"):
        manager.create("other", questions, request_id="A")
    answers = [["original answer"]]
    manager.reply("A", answers)
    answers[0][0] = "changed answer"
    assert pending.questions == [{"question": "original"}]
    assert pending.answers == [["original answer"]]


@pytest.mark.asyncio
async def test_reply_endpoint_reports_mismatched_count_and_preserves_pending(
    monkeypatch,
):
    manager = QuestionManager()
    monkeypatch.setattr(
        "dbgpt_app.openapi.api_v1.tools.question_manager.question_manager", manager
    )
    pending = manager.create(
        "conversation", [{"question": "first"}, {"question": "second"}], request_id="A"
    )
    response = await agentic_data_api.question_reply(
        "A", agentic_data_api._QuestionReplyBody(answers=[["shifted"]]), None
    )
    assert response.success is False
    assert not pending.event.is_set()
    response = await agentic_data_api.question_reply(
        "A", agentic_data_api._QuestionReplyBody(answers=[["first"], ["second"]]), None
    )
    assert response.success is True
    assert response.data["request_id"] == "A"
    assert pending.answers == [["first"], ["second"]]
