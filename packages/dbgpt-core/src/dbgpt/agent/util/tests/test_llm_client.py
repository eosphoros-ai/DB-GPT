"""Tests for the token metadata recorded by AIWrapper on its tracing span."""

import json
from dataclasses import asdict
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


@pytest.mark.asyncio
async def test_span_total_tokens_from_metrics_with_partial_usage(monkeypatch):
    from dbgpt.model.cluster.worker.default_worker import (
        _new_metrics_from_model_output,
    )

    # Usage as sent by the Claude proxy: no total_tokens.
    usage = {"prompt_tokens": 11, "completion_tokens": 7}
    last_metrics = ModelInferenceMetrics.create_metrics()
    # Start one second earlier so the speed calculation has a non-zero duration.
    last_metrics.start_time_ms -= 1000
    metrics = _new_metrics_from_model_output(last_metrics, True, usage)
    output = ModelOutput.build("hi", usage=usage, metrics=metrics)

    span = await _run_and_get_span(output, monkeypatch)

    assert span.metadata["prompt_tokens"] == 11
    assert span.metadata["completion_tokens"] == 7
    assert span.metadata["total_tokens"] == 18


@pytest.mark.asyncio
async def test_span_tokens_from_metrics_dict_of_remote_worker(monkeypatch):
    usage = {"prompt_tokens": 11, "completion_tokens": 7}
    metrics = ModelInferenceMetrics(
        prompt_tokens=11, completion_tokens=7, total_tokens=18
    )
    output = ModelOutput.build("hi", usage=usage, metrics=metrics)
    # Remote workers send outputs as JSON, so ``metrics`` comes back as a dict.
    output = ModelOutput(**json.loads(json.dumps(asdict(output))))
    assert isinstance(output.metrics, dict)

    span = await _run_and_get_span(output, monkeypatch)

    assert span.metadata["prompt_tokens"] == 11
    assert span.metadata["completion_tokens"] == 7
    assert span.metadata["total_tokens"] == 18
