"""Tests for native function calling support in the model interface layer."""

from dbgpt.core.interface.llm import ModelOutput, ModelRequest
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType


def test_assistant_and_tool_message_round_trip():
    msgs = ModelMessage.from_openai_messages(
        [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "add", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "42"},
        ]
    )
    assert msgs[0].role == ModelMessageRoleType.AI
    assert msgs[0].tool_calls[0]["function"]["name"] == "add"
    assert msgs[1].role == ModelMessageRoleType.TOOL
    assert msgs[1].tool_call_id == "c1"
    assert msgs[1].pass_to_model is True

    common = ModelMessage.to_common_messages(msgs)
    assert common[0]["role"] == "assistant"
    assert common[0]["tool_calls"][0]["function"]["name"] == "add"
    assert common[1]["role"] == "tool"
    assert common[1]["tool_call_id"] == "c1"
    assert common[1]["content"] == "42"


def test_legacy_function_role_maps_to_tool():
    msgs = ModelMessage.from_openai_messages(
        [{"role": "function", "name": "add", "content": "42"}]
    )
    assert msgs[0].role == ModelMessageRoleType.TOOL
    assert msgs[0].tool_call_id == "add"


def test_model_output_carries_tool_calls():
    out = ModelOutput.build(
        "hi",
        tool_calls=[
            {
                "id": "1",
                "type": "function",
                "function": {"name": "add", "arguments": "{}"},
            }
        ],
    )
    assert out.tool_calls[0]["function"]["name"] == "add"
    assert out.to_dict()["tool_calls"][0]["function"]["name"] == "add"


def test_model_request_carries_tools():
    req = ModelRequest(
        model="m",
        messages=[ModelMessage(role=ModelMessageRoleType.HUMAN, content="hi")],
        tools=[{"type": "function", "function": {"name": "add", "parameters": {}}}],
        tool_choice="auto",
    )
    assert req.tools[0]["function"]["name"] == "add"
    assert req.tool_choice == "auto"
    d = req.to_dict()
    assert d["tools"][0]["function"]["name"] == "add"
    assert d["tool_choice"] == "auto"
