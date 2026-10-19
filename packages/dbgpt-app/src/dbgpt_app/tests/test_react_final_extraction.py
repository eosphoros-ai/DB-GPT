"""Final answers must honor the registered terminate schema and legacy inputs."""

import json

import pytest

from dbgpt.agent.expand.actions.react_action import ReActAction, Terminate
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt_app.openapi.api_v1.react_final import extract_terminate_content


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["output", "result", "final_answer"])
@pytest.mark.parametrize("envelope", ["react", "json", "repr"])
async def test_terminate_answer_excludes_reasoning_and_argument_envelope(key, envelope):
    answer = "本期营业收入为{{fact:revenue}}。\n依据可在右侧报告中核对。"
    payload = {key: answer}
    raw = repr(payload) if envelope == "repr" else json.dumps(payload)
    if envelope == "react":
        raw = "Thought: 已核对金额999元。\nAction: terminate\nAction Input: " + raw
    action_output = await Terminate().run(raw)
    assert action_output.terminate
    assert (
        extract_terminate_content(action_output.content, ReActOutputParser()) == answer
    )


@pytest.mark.asyncio
async def test_core_thought_only_terminal_fallback_does_not_leak_protocol_prefix():
    output = await ReActAction().run("Thought: routing-general-ok")
    assert output.terminate
    assert (
        extract_terminate_content(output.content, ReActOutputParser())
        == "routing-general-ok"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "普通回答，保留完整正文。",
        "{}",
        '{"output": 42}',
        '{"output": "未闭合',
        'Action: other_tool\nAction Input: {"output": "不是最终回答"}',
    ],
)
def test_plain_or_invalid_terminate_content_is_preserved_for_validation(raw):
    assert extract_terminate_content(raw, ReActOutputParser()) == raw
