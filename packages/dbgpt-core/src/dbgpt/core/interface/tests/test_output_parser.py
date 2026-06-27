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
