from typing import AsyncIterator, Dict
import logging
from pilot.awel import (
    StreamifyAbsOperator,
    MapOperator,
    TransformStreamAbsOperator,
)
from pilot.model.base import ModelOutput
from pilot.model.cluster import WorkerManager
from pilot.cache import LLMCacheClient, CacheManager, LLMCacheKey, LLMCacheValue

logger = logging.getLogger(__name__)

_LLM_MODEL_INPUT_VALUE_KEY = "llm_model_input_value"
_LLM_MODEL_OUTPUT_CACHE_KEY = "llm_model_output_cache"


class ModelStreamOperator(StreamifyAbsOperator[Dict, ModelOutput]):
    def __init__(self, worker_manager: WorkerManager, **kwargs) -> None:
        super().__init__(**kwargs)
        self.worker_manager = worker_manager

    async def streamify(self, input_value: Dict) -> AsyncIterator[ModelOutput]:
        llm_cache_value: LLMCacheValue = await self.current_dag_context.get_share_data(
            _LLM_MODEL_OUTPUT_CACHE_KEY
        )
        logger.info(f"llm_cache_value: {llm_cache_value}")
        if llm_cache_value:
            for out in llm_cache_value.get_value().output:
                yield out
            return
        async for out in self.worker_manager.generate_stream(input_value):
            yield out


class ModelOperator(MapOperator[Dict, ModelOutput]):
    def __init__(self, worker_manager: WorkerManager, **kwargs) -> None:
        self.worker_manager = worker_manager
        super().__init__(**kwargs)

    async def map(self, input_value: Dict) -> ModelOutput:
        llm_cache_value: LLMCacheValue = await self.current_dag_context.get_share_data(
            _LLM_MODEL_OUTPUT_CACHE_KEY
        )
        logger.info(f"llm_cache_value: {llm_cache_value}")
        if llm_cache_value:
            return llm_cache_value.get_value().output
        return await self.worker_manager.generate(input_value)


class ModelCachePreOperator(MapOperator[Dict, Dict]):
    def __init__(self, cache_manager: CacheManager, **kwargs):
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)
        super().__init__(**kwargs)

    async def map(self, input_value: Dict) -> Dict:
        cache_dict = {
            "prompt": input_value.get("prompt"),
            "model_name": input_value.get("model"),
            "temperature": input_value.get("temperature"),
            "max_new_tokens": input_value.get("max_new_tokens"),
            "top_p": input_value.get("top_p", "1.0"),
            # TODO pass model_type
            "model_type": input_value.get("model_type", "huggingface"),
        }
        cache_key: LLMCacheKey = self._client.new_key(**cache_dict)
        cache_value = await self._client.get(cache_key)
        logger.debug(
            f"cache_key: {cache_key}, hash key: {hash(cache_key)}, cache_value: {cache_value}"
        )
        await self.current_dag_context.save_to_share_data(
            _LLM_MODEL_INPUT_VALUE_KEY, cache_key
        )
        if cache_value:
            logger.info(f"The model output has cached, cache_value: {cache_value}")
            await self.current_dag_context.save_to_share_data(
                _LLM_MODEL_OUTPUT_CACHE_KEY, cache_value
            )
        return input_value


class ModelStreamCacheOperator(TransformStreamAbsOperator[ModelOutput, ModelOutput]):
    def __init__(self, cache_manager: CacheManager, **kwargs):
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)
        super().__init__(**kwargs)

    async def transform_stream(
        self, input_value: AsyncIterator[ModelOutput]
    ) -> AsyncIterator[ModelOutput]:
        llm_cache_key: LLMCacheKey = None
        outputs = []
        async for out in input_value:
            if not llm_cache_key:
                llm_cache_key = await self.current_dag_context.get_share_data(
                    _LLM_MODEL_INPUT_VALUE_KEY
                )
            outputs.append(out)
            yield out
        if llm_cache_key:
            llm_cache_value: LLMCacheValue = self._client.new_value(output=outputs)
            await self._client.set(llm_cache_key, llm_cache_value)


class ModelCacheOperator(MapOperator[ModelOutput, ModelOutput]):
    def __init__(self, cache_manager: CacheManager, **kwargs):
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)
        super().__init__(**kwargs)

    async def map(self, input_value: ModelOutput) -> ModelOutput:
        llm_cache_key: LLMCacheKey = await self.current_dag_context.get_share_data(
            _LLM_MODEL_INPUT_VALUE_KEY
        )
        llm_cache_value: LLMCacheValue = self._client.new_value(output=input_value)
        if llm_cache_key:
            await self._client.set(llm_cache_key, llm_cache_value)
        return input_value
