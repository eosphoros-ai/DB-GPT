from typing import AsyncIterator, List
import asyncio
from dbgpt.core.interface.llm import LLMClient, ModelRequest, ModelOutput, ModelMetadata
from dbgpt.model.parameter import WorkerType
from dbgpt.model.cluster.manager_base import WorkerManager


class DefaultLLMClient(LLMClient):
    def __init__(self, worker_manager: WorkerManager):
        self._worker_manager = worker_manager

    async def generate(self, request: ModelRequest) -> ModelOutput:
        return await self._worker_manager.generate(request.to_dict())

    async def generate_stream(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelOutput]:
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
