import asyncio
from typing import AsyncIterator, List, Optional

from dbgpt.core.interface.llm import (
    DefaultMessageConverter,
    LLMClient,
    MessageConverter,
    ModelMetadata,
    ModelOutput,
    ModelRequest,
)
from dbgpt.model.cluster.manager_base import WorkerManager
from dbgpt.model.parameter import WorkerType


class DefaultLLMClient(LLMClient):
    """Default LLM client implementation.

    Connect to the worker manager and send the request to the worker manager.

    Args:
        worker_manager (WorkerManager): worker manager instance.
        auto_convert_message (bool, optional): auto convert the message to ModelRequest. Defaults to False.
    """

    def __init__(
        self, worker_manager: WorkerManager, auto_convert_message: bool = False
    ):
        self._worker_manager = worker_manager
        self._auto_covert_message = auto_convert_message

    async def generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        if not message_converter and self._auto_covert_message:
            message_converter = DefaultMessageConverter()
        request = await self.covert_message(request, message_converter)
        return await self._worker_manager.generate(request.to_dict())

    async def generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> AsyncIterator[ModelOutput]:
        if not message_converter and self._auto_covert_message:
            message_converter = DefaultMessageConverter()
        request = await self.covert_message(request, message_converter)
        async for output in self._worker_manager.generate_stream(request.to_dict()):
            yield output

    async def models(self) -> List[ModelMetadata]:
        instances = await self._worker_manager.get_all_model_instances(
            WorkerType.LLM.value, healthy_only=True
        )
        query_metadata_task = []
        for instance in instances:
            worker_name, _ = WorkerType.parse_worker_key(instance.worker_key)
            query_metadata_task.append(
                self._worker_manager.get_model_metadata({"model": worker_name})
            )
        models: List[ModelMetadata] = await asyncio.gather(*query_metadata_task)
        model_map = {}
        for single_model in models:
            model_map[single_model.model] = single_model
        return [model_map[model_name] for model_name in sorted(model_map.keys())]

    async def count_token(self, model: str, prompt: str) -> int:
        return await self._worker_manager.count_token(
            {"model": model, "prompt": prompt}
        )
