"""Tests for :class:`BaseOutputParser.parse_prompt_response`."""

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
