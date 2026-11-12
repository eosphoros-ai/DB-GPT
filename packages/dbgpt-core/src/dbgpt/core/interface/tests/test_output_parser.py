"""Tests for :class:`BaseOutputParser`."""

import pytest

from dbgpt.core import ModelOutput
from dbgpt.core.awel import DAG, StreamifyAbsOperator
from dbgpt.core.interface.output_parser import BaseOutputParser, SQLListOutputParser


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


def test_parse_model_stream_resp_ex_returns_text():
    """A successful chunk is returned as its stripped text."""
    parser = _parser()
    output = ModelOutput(text="  SELECT 1  ", error_code=0)
    assert parser.parse_model_stream_resp_ex(output) == "SELECT 1"


def test_parse_model_stream_resp_ex_error_chunk():
    """A failed chunk keeps its text and reports the error code."""
    parser = _parser()
    output = ModelOutput(text="model error", error_code=1)
    assert parser.parse_model_stream_resp_ex(output) == "model error (error_code: 1)"


class _ModelOutputStream(StreamifyAbsOperator[str, ModelOutput]):
    async def streamify(self, input_value: str):
        for text in ["Hello", "Hello world"]:
            yield ModelOutput(text=text, error_code=0)


@pytest.mark.asyncio
async def test_streaming_call_outputs_text():
    """In a streaming DAG call every chunk is parsed to its text."""
    with DAG("test_output_parser_streaming_dag"):
        source = _ModelOutputStream()
        parser = BaseOutputParser()
        source >> parser

    outputs = [out async for out in await parser.call_stream("input")]
    assert outputs == ["Hello", "Hello world"]


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
def test_sql_list_parser_preserves_raw_line_endings(newline):
    """Lenient model output must preserve CR and CRLF as well as LF."""
    content = "select 1" + newline + "from example"
    response = '```json\n[{"sql":"' + content + '"}]\n```'

    result = SQLListOutputParser().parse_model_nostream_resp(
        ModelOutput(text=response, error_code=0)
    )

    assert result == [{"sql": content}]
