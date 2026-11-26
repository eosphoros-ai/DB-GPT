"""Proxy workers expose adapter windows instead of the worker default."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dbgpt.core import ModelMetadata
from dbgpt.model.cluster.worker.default_worker import DefaultModelWorker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,worker_window,expected,expected_source",
    [
        ("fallback", 4096, 1048576, "adapter_metadata"),
        ("deployment_config", 65536, 65536, "deployment_config"),
    ],
)
async def test_proxy_metadata_preserves_deployment_override(
    source, worker_window, expected, expected_source
):
    # Avoid loading a real model or requiring torch/GPU.
    worker = DefaultModelWorker.__new__(DefaultModelWorker)
    worker.model_name = "alias"
    worker.context_len = worker_window
    worker._context_length_source = source
    worker.llm_adapter = SimpleNamespace(
        get_prompt_roles=lambda: ["system", "human", "ai"],
        get_default_message_separator=lambda: "\n",
    )
    proxy = SimpleNamespace(
        default_model="provider-model",
        get_model_metadata=AsyncMock(
            return_value=ModelMetadata(
                model="provider-model",
                context_length=1048576,
                max_output_length=8192,
                metadata={"context_length_source": "adapter_metadata"},
            )
        ),
    )
    worker.model = SimpleNamespace(proxy_llm_client=proxy)
    metadata = await worker.async_get_model_metadata({})
    assert metadata.model == "alias"
    assert metadata.context_length == expected
    assert metadata.metadata["context_length_source"] == expected_source
    assert metadata.max_output_length == 8192
    proxy.get_model_metadata.assert_awaited_once_with("provider-model")
