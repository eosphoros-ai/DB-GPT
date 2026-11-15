"""Tests for the token metadata recorded by AIWrapper on its tracing span."""

from typing import List

import pytest

from dbgpt.agent.util.llm import llm_client as llm_client_module
from dbgpt.agent.util.llm.llm_client import AIWrapper
from dbgpt.core import LLMClient, ModelMetadata, ModelOutput
from dbgpt.core.interface.llm import ModelInferenceMetrics
from dbgpt.util.tracer import Span


class _FakeLLMClient(LLMClient):
    def __init__(self, output: ModelOutput):
        self._output = output

    async def generate(self, request, message_converter=None):
        return self._output

    async def generate_stream(self, request, message_converter=None):
        yield self._output

    async def models(self) -> List[ModelMetadata]:
        return []

    async def count_token(self, model: str, prompt: str) -> int:
        return 0


async def _run_and_get_span(output: ModelOutput, monkeypatch) -> Span:
    spans: List[Span] = []
    original_start_span = llm_client_module.root_tracer.start_span

    def _start_span(*args, **kwargs):
        span = original_start_span(*args, **kwargs)
        spans.append(span)
        return span

    monkeypatch.setattr(llm_client_module.root_tracer, "start_span", _start_span)
    wrapper = AIWrapper(_FakeLLMClient(output))
    await wrapper.create(
        messages=[{"role": "user", "content": "hello"}],
        llm_model="test-model",
        temperature=0.5,
        max_new_tokens=128,
        stream_out=False,
    )
    assert len(spans) == 1
    return spans[0]


@pytest.mark.asyncio
async def test_span_tokens_fall_back_to_metrics_without_usage(monkeypatch):
    metrics = ModelInferenceMetrics(
        prompt_tokens=11, completion_tokens=7, total_tokens=18
    )
    output = ModelOutput.build("hi", metrics=metrics)

    span = await _run_and_get_span(output, monkeypatch)

    assert span.metadata["prompt_tokens"] == 11
    assert span.metadata["completion_tokens"] == 7
    assert span.metadata["total_tokens"] == 18


@pytest.mark.asyncio
async def test_span_tokens_prefer_usage_over_metrics(monkeypatch):
    metrics = ModelInferenceMetrics(
        prompt_tokens=11, completion_tokens=7, total_tokens=18
    )
    usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    output = ModelOutput.build("hi", usage=usage, metrics=metrics)

    span = await _run_and_get_span(output, monkeypatch)

    assert span.metadata["prompt_tokens"] == 3
    assert span.metadata["completion_tokens"] == 2
    assert span.metadata["total_tokens"] == 5
