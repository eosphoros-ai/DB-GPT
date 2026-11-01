"""Tests for :class:`BaseOutputParser.parse_prompt_response`."""

import json

import pytest

from dbgpt.core.interface.output_parser import BaseOutputParser


def _parser() -> BaseOutputParser:
    return BaseOutputParser(is_stream_out=False)


def test_parse_prompt_response_single_json_fence():
    """A single ```json fence is unwrapped to the inner object."""
    parser = _parser()
    text = '```json\n{"a": 1}\n```'
    assert parser.parse_prompt_response(text) == '{"a": 1}'


def test_parse_prompt_response_multiple_json_fences():
    """Multiple ```json fences must not raise 'too many values to unpack'.

    A model response can contain more than one ```json code block (e.g. an
    explanation followed by the answer, or chain-of-thought style output).
    The old ``split("```json")`` unpacked into exactly two names and raised a
    ``ValueError`` in that case; we now split on the first fence only.
    """
    parser = _parser()
    text = 'First ```json\n{"a": 1}\n``` then ```json\n{"b": 2}\n```'
    # Must not raise; everything after the first fence is kept for downstream
    # extraction.
    result = parser.parse_prompt_response(text)
    assert isinstance(result, str)
    assert '{"a": 1}' in result


def test_parse_prompt_response_no_fence():
    """Plain JSON without a fence is returned unchanged."""
    parser = _parser()
    assert parser.parse_prompt_response('{"a": 1}') == '{"a": 1}'


def test_parse_prompt_response_brace_inside_string_value():
    """A ``}`` inside a JSON string must not terminate the object early.

    ``_json_interception`` counted raw ``{``/``}`` characters without tracking
    string literals, so a SQL payload such as
    ``json_extract(col, '$.a}')`` closed the object at the brace inside the
    string. The returned text was then truncated mid-token and downstream
    ``json.loads`` failed, surfacing as "Failed to find a valid json in LLM
    response".
    """
    parser = _parser()
    text = (
        'Here is the SQL:\n{"sql": "SELECT json_extract(col, \'$.a}\') FROM t"}\nDone.'
    )
    assert parser.parse_prompt_response(text) == (
        '{"sql": "SELECT json_extract(col, \'$.a}\') FROM t"}'
    )


def test_parse_prompt_response_bracket_inside_string_value():
    """The same early-termination bug applies to ``]`` in the array branch."""
    parser = _parser()
    text = 'Result:\n["a]b", "c"]\nDone.'
    assert parser.parse_prompt_response(text) == '["a]b", "c"]'


def test_parse_prompt_response_escaped_quote_inside_string_value():
    """A backslash-escaped quote must not end the JSON string."""
    parser = _parser()
    text = 'Result:\n{"sql": "SELECT \\"x\\" FROM t"}\nDone.'
    assert parser.parse_prompt_response(text) == ('{"sql": "SELECT \\"x\\" FROM t"}')


def test_parse_prompt_response_escaped_backslash_before_closing_quote():
    """``\\\\`` inside a string is data, so the following quote still closes it."""
    parser = _parser()
    text = 'Result:\n{"path": "C:\\\\"}\nDone.'
    result = parser.parse_prompt_response(text)
    assert result == '{"path": "C:\\\\"}'
    assert json.loads(result) == {"path": "C:\\"}


@pytest.mark.parametrize(
    "text",
    [
        'Result: {"a": 1',
        'Result: ["a", "b"',
        'Result: {"a": "unterminated',
    ],
)
def test_parse_prompt_response_unterminated_input_is_returned_unchanged(text):
    """Unterminated JSON falls back to the raw model output, not a fragment.

    ``_json_interception`` returns ``""`` for an unterminated object/array, and
    ``parse_prompt_response`` then returns the original text. The important
    part is that no truncated fragment is handed to ``json.loads``.
    """
    parser = _parser()
    assert parser._json_interception(text) == ""
    assert parser.parse_prompt_response(text) == text


def test_parse_prompt_response_prefers_a_parsable_fragment():
    """A longer but unparsable array must not hide a valid object.

    The array branch now ignores ``]`` inside strings, so its fragment can grow
    past the object one, and ``_extract_json`` used to take the longest
    candidate. That made previously-parsed outputs fail.
    """
    parser = _parser()
    text = 'Result: [ "a]b" oops ] {"ok": true}'
    assert parser.parse_prompt_response(text) == '{"ok": true}'


def test_parse_prompt_response_keeps_literal_newline_object():
    """A candidate is validated with the same normalization as downstream.

    ``parse_prompt_response`` replaces newlines after extracting, so an object
    holding a real newline still parses; the parsable-candidate check must not
    drop it in favour of a nested array.
    """
    parser = _parser()
    text = 'Result: {"sql": "SELECT\n1", "columns": ["x"]}'
    assert parser.parse_prompt_response(text) == (
        '{"sql": "SELECT 1", "columns": ["x"]}'
    )


def test_parse_prompt_response_does_not_promote_nested_fragment():
    """An invalid array must not be replaced by an object nested inside it."""
    parser = _parser()
    text = 'Result: [{"sql":"SELECT 1"},{"sql": invalid}]'
    assert parser.parse_prompt_response(text) == text[len("Result: ") :]


def test_parse_prompt_response_keeps_array_tie_breaker():
    """Equal-length candidates still resolve to the array, as before."""
    parser = _parser()
    text = "Result: {\"a\":1}; answer: [1,2,3]"
    assert parser.parse_prompt_response(text) == "[1,2,3]"


def test_parse_prompt_response_promotes_independent_duplicate():
    """An identical fragment outside the invalid container is still promoted."""
    parser = _parser()
    text = 'Result: {"ok": true} [ {"ok": true}, invalid ]'
    assert parser.parse_prompt_response(text) == '{"ok": true}'
