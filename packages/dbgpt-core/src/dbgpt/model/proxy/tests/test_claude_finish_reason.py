import pytest

from dbgpt.core.schema.api import (
    ChatCompletionResponseChoice,
    ChatCompletionResponseStreamChoice,
    ChatMessage,
    DeltaMessage,
)
from dbgpt.model.proxy.llms.claude import _to_finish_reason


@pytest.mark.parametrize(
    "stop_reason,expected",
    [
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("max_tokens", "length"),
        ("tool_use", "tool_calls"),
        ("refusal", "content_filter"),
        ("something_new", "stop"),
        (None, None),
    ],
)
def test_claude_stop_reason_maps_to_a_valid_finish_reason(stop_reason, expected):
    finish_reason = _to_finish_reason(stop_reason)
    assert finish_reason == expected
    choice = ChatCompletionResponseChoice(
        index=0,
        message=ChatMessage(role="assistant", content="hi"),
        finish_reason=finish_reason,
    )
    assert choice.finish_reason == expected


@pytest.mark.parametrize("finish_reason", ["tool_calls", "content_filter"])
def test_response_choices_accept_openai_finish_reasons(finish_reason):
    stream_choice = ChatCompletionResponseStreamChoice(
        index=0, delta=DeltaMessage(content=""), finish_reason=finish_reason
    )
    assert stream_choice.finish_reason == finish_reason
