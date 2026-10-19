import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dbgpt_app.openapi.api_v1.dashboard.annotation_intents import (
    AnnotationIntentBatch,
    resolve_annotation_intents,
    validate_intent_resolution,
)


def batch(*prompts):
    return AnnotationIntentBatch(
        items=[
            {
                "draft_id": str(index),
                "prompt": prompt,
                "target": {
                    "kind": "widget",
                    "widget_id": "revenue",
                    "label": "商品净收入",
                },
            }
            for index, prompt in enumerate(prompts)
        ],
        model="chosen-model",
    )


def result(draft_id, intent="explain", prompt="解释计算口径"):
    return {
        "draft_id": draft_id,
        "tasks": [{"intent": intent, "prompt": prompt}],
        "question": None,
    }


@pytest.mark.asyncio
async def test_uses_selected_model_and_keeps_negation_and_mixed_requests():
    request = batch("不要修改图表，只解释净收入怎么算", "改成柱状图，并解释下降原因")
    output = {
        "items": [
            result("0"),
            {
                "draft_id": "1",
                "tasks": [
                    {"intent": "modify", "prompt": "改成柱状图"},
                    {"intent": "anomaly", "prompt": "解释下降原因"},
                ],
            },
        ]
    }
    client = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(error_code=0, text=json.dumps(output))
        )
    )
    resolved = await resolve_annotation_intents(request, client)
    sent = client.generate.call_args.args[0]
    assert sent.model == "chosen-model"
    assert "不要修改图表" in sent.messages[1].content
    assert resolved.items[0].tasks[0].intent.value == "explain"
    assert [task.intent.value for task in resolved.items[1].tasks] == [
        "modify",
        "anomaly",
    ]


@pytest.mark.parametrize(
    "items",
    [
        [result("0")],
        [result("0"), result("0")],
        [result("0"), result("unknown")],
        [result("0"), {"draft_id": "1", "tasks": []}],
        [result("0"), {**result("1"), "question": "同时执行？"}],
        [result("0"), result("1", "delete_database")],
    ],
)
def test_rejects_incomplete_duplicate_or_invalid_routing(items):
    with pytest.raises(ValueError):
        validate_intent_resolution(json.dumps({"items": items}), batch("解释", "修改"))


def test_ambiguity_remains_a_question_without_a_default_modify_intent():
    resolved = validate_intent_resolution(
        json.dumps(
            {
                "items": [
                    {
                        "draft_id": "0",
                        "tasks": [],
                        "question": "你希望调整图表展示，还是核对指标口径？",
                    }
                ]
            }
        ),
        batch("这个不对"),
    )
    assert resolved.items[0].question
    assert resolved.items[0].tasks == []


@pytest.mark.asyncio
async def test_model_failure_does_not_fall_back_to_modifying():
    client = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(error_code=1, text="unavailable")
        )
    )
    with pytest.raises(ValueError, match="暂时无法识别"):
        await resolve_annotation_intents(batch("怎么算的"), client)


@pytest.mark.asyncio
async def test_conversation_and_live_view_reach_model_and_advice_needs_no_task():
    request = batch("你觉得有什么改进的地方吗")
    request.message = "那就先看看选中的几个"
    request.conversation = "assistant: 可以检查客户数与市场覆盖的口径。"
    request.view_context = {
        "filter_values": {"year": "1997"},
        "widgets": [{"id": "revenue", "rows_sample": [{"value": 42}]}],
    }
    response = {
        "reply": "先看商品净收入：建议在标题补充当前年份，便于理解筛选范围。",
        "items": [{"draft_id": "0", "tasks": [], "answered": True}],
    }
    client = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(error_code=0, text=json.dumps(response))
        )
    )
    resolved = await resolve_annotation_intents(
        request, client, dashboard_context={"title": "品牌营收驾驶舱"}
    )
    sent = client.generate.call_args.args[0]
    context = json.loads(sent.messages[1].content)
    assert context["saved_dashboard"]["title"] == "品牌营收驾驶舱"
    assert context["current_view"]["filter_values"]["year"] == "1997"
    assert context["conversation"] == request.conversation
    assert context["items"][0]["target"]["widget_id"] == "revenue"
    assert (
        "不要反问" in sent.messages[0].content
    )  # The project skill is actually injected.
    assert resolved.reply == response["reply"]
    assert resolved.items[0].answered
    assert resolved.model == "chosen-model"


def test_clear_tasks_can_coexist_with_one_specific_question():
    output = {
        "reply": "可以先调整收入图；客户口径还需要区分下单和注册。",
        "items": [
            result("0", "modify", "把收入图改为折线图"),
            {
                "draft_id": "1",
                "tasks": [],
                "question": "客户是指下单客户还是注册客户？",
            },
        ],
    }
    resolved = validate_intent_resolution(
        json.dumps(output), batch("改为折线图", "客户不对")
    )
    assert resolved.items[0].tasks[0].intent.value == "modify"
    assert resolved.items[1].question


@pytest.mark.parametrize("reply", [None, "", "   "])
def test_answered_without_actual_answer_is_invalid(reply):
    with pytest.raises(ValueError, match="未返回回答"):
        validate_intent_resolution(
            json.dumps(
                {
                    "reply": reply,
                    "items": [{"draft_id": "0", "tasks": [], "answered": True}],
                }
            ),
            batch("看看"),
        )


@pytest.mark.asyncio
async def test_repairs_model_output_format_once_without_defaulting_to_modify():
    malformed = {
        "items": [
            {
                "draft_id": "0",
                "tasks": [{"type": "explain", "prompt": "解释净收入口径"}],
            }
        ]
    }
    valid = {"items": [result("0")]}
    client = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                SimpleNamespace(error_code=0, text=json.dumps(malformed)),
                SimpleNamespace(error_code=0, text=json.dumps(valid)),
            ]
        )
    )
    resolved = await resolve_annotation_intents(batch("不要改，只解释口径"), client)
    assert resolved.items[0].tasks[0].intent.value == "explain"
    assert client.generate.await_count == 2
    repaired = json.loads(client.generate.call_args_list[1].args[0].messages[1].content)
    assert repaired["items"][0]["prompt"] == "不要改，只解释口径"
    assert "format_repair" in repaired


@pytest.mark.asyncio
async def test_repeated_invalid_output_fails_without_loop_or_manufactured_task():
    client = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(error_code=0, text='{"items":[]}')
        )
    )
    with pytest.raises(ValueError):
        await resolve_annotation_intents(batch("先不要修改"), client)
    assert client.generate.await_count == 2
