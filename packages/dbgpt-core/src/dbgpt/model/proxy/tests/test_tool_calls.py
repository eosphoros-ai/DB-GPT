"""Tests for streaming tool_calls merging (native function calling)."""

from dbgpt.model.proxy.llms.chatgpt import merge_streaming_tool_calls


def test_merge_single_tool_call_across_fragments():
    deltas = [
        {
            "index": 0,
            "id": "call_1",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a": '},
        },
        {"index": 0, "function": {"arguments": '1, "b": 2}'}},
    ]
    merged = merge_streaming_tool_calls(None, deltas)
    assert len(merged) == 1
    assert merged[0]["id"] == "call_1"
    assert merged[0]["function"]["name"] == "add"
    assert merged[0]["function"]["arguments"] == '{"a": 1, "b": 2}'


def test_merge_multiple_tool_calls_by_index():
    deltas = [
        {"index": 0, "id": "c0", "function": {"name": "add", "arguments": "{}"}},
        {
            "index": 1,
            "id": "c1",
            "function": {"name": "multiply", "arguments": '{"x":'},
        },
        {"index": 1, "function": {"arguments": "1}"}},
    ]
    merged = merge_streaming_tool_calls(None, deltas)
    assert [m["id"] for m in merged] == ["c0", "c1"]
    assert merged[1]["function"]["name"] == "multiply"
    assert merged[1]["function"]["arguments"] == '{"x":1}'


def test_merge_dict_arguments_stringified():
    deltas = [
        {
            "index": 0,
            "function": {"name": "f", "arguments": {"a": 1}},
        }
    ]
    merged = merge_streaming_tool_calls(None, deltas)
    assert merged[0]["function"]["arguments"] == '{"a": 1}'


def test_merge_none_deltas_noop():
    assert merge_streaming_tool_calls(None, None) == []
