from typing import AsyncIterator, Dict, List, Union
import logging
from dbgpt.core.awel import (
    BranchFunc,
    StreamifyAbsOperator,
    BranchOperator,
    MapOperator,
    TransformStreamAbsOperator,
)
from dbgpt.component import ComponentType
from dbgpt.core.awel.operator.base import BaseOperator
from dbgpt.core import ModelOutput
from dbgpt.model.cluster import WorkerManager, WorkerManagerFactory
from dbgpt.storage.cache import LLMCacheClient, CacheManager, LLMCacheKey, LLMCacheValue

logger = logging.getLogger(__name__)

_LLM_MODEL_INPUT_VALUE_KEY = "llm_model_input_value"
_LLM_MODEL_OUTPUT_CACHE_KEY = "llm_model_output_cache"


class ModelStreamOperator(StreamifyAbsOperator[Dict, ModelOutput]):
    """Operator for streaming processing of model outputs.

    Args:
        worker_manager (WorkerManager): The manager that handles worker processes for model inference.
        **kwargs: Additional keyword arguments.

    Methods:
        streamify: Asynchronously processes a stream of inputs, yielding model outputs.
    """

    def __init__(self, worker_manager: WorkerManager = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.worker_manager = worker_manager

    async def streamify(self, input_value: Dict) -> AsyncIterator[ModelOutput]:
        """Process inputs as a stream and yield model outputs.

        Args:
            input_value (Dict): The input value for the model.

        Returns:
            AsyncIterator[ModelOutput]: An asynchronous iterator of model outputs.
        """
        if not self.worker_manager:
            self.worker_manager = self.system_app.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
        async for out in self.worker_manager.generate_stream(input_value):
            yield out


class ModelOperator(MapOperator[Dict, ModelOutput]):
    """Operator for map-based processing of model outputs.

    Args:
        worker_manager (WorkerManager): Manager for handling worker processes.
        **kwargs: Additional keyword arguments.

    Methods:
        map: Asynchronously processes a single input and returns the model output.
    """

    def __init__(self, worker_manager: WorkerManager = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.worker_manager = worker_manager

    async def map(self, input_value: Dict) -> ModelOutput:
        """Process a single input and return the model output.

        Args:
            input_value (Dict): The input value for the model.

        Returns:
            ModelOutput: The output from the model.
        """
        if not self.worker_manager:
            self.worker_manager = self.system_app.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
        return await self.worker_manager.generate(input_value)


class CachedModelStreamOperator(StreamifyAbsOperator[Dict, ModelOutput]):
    """Operator for streaming processing of model outputs with caching.

    Args:
        cache_manager (CacheManager): The cache manager to handle caching operations.
        **kwargs: Additional keyword arguments.

    Methods:
        streamify: Processes a stream of inputs with cache support, yielding model outputs.
    """

    def __init__(self, cache_manager: CacheManager, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)

    async def streamify(self, input_value: Dict) -> AsyncIterator[ModelOutput]:
        """Process inputs as a stream with cache support and yield model outputs.

        Args:
            input_value (Dict): The input value for the model.

        Returns:
            AsyncIterator[ModelOutput]: An asynchronous iterator of model outputs.
        """
        cache_dict = _parse_cache_key_dict(input_value)
        llm_cache_key: LLMCacheKey = self._client.new_key(**cache_dict)
        llm_cache_value: LLMCacheValue = await self._client.get(llm_cache_key)
        logger.info(f"llm_cache_value: {llm_cache_value}")
        for out in llm_cache_value.get_value().output:
            yield out


class CachedModelOperator(MapOperator[Dict, ModelOutput]):
    """Operator for map-based processing of model outputs with caching.

    Args:
        cache_manager (CacheManager): Manager for caching operations.
        **kwargs: Additional keyword arguments.

    Methods:
        map: Processes a single input with cache support and returns the model output.
    """

    def __init__(self, cache_manager: CacheManager, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)

    async def map(self, input_value: Dict) -> ModelOutput:
        """Process a single input with cache support and return the model output.

        Args:
            input_value (Dict): The input value for the model.

        Returns:
            ModelOutput: The output from the model.
        """
        cache_dict = _parse_cache_key_dict(input_value)
        llm_cache_key: LLMCacheKey = self._client.new_key(**cache_dict)
        llm_cache_value: LLMCacheValue = await self._client.get(llm_cache_key)
        logger.info(f"llm_cache_value: {llm_cache_value}")
        return llm_cache_value.get_value().output


class ModelCacheBranchOperator(BranchOperator[Dict, Dict]):
    """
    A branch operator that decides whether to use cached data or to process data using the model.

    Args:
        cache_manager (CacheManager): The cache manager for managing cache operations.
        model_task_name (str): The name of the task to process data using the model.
        cache_task_name (str): The name of the task to process data using the cache.
        **kwargs: Additional keyword arguments.
    """

    def __init__(
        self,
        cache_manager: CacheManager,
        model_task_name: str,
        cache_task_name: str,
        **kwargs,
    ):
        super().__init__(branches=None, **kwargs)
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)
        self._model_task_name = model_task_name
        self._cache_task_name = cache_task_name

    async def branchs(self) -> Dict[BranchFunc[Dict], Union[BaseOperator, str]]:
        """Defines branch logic based on cache availability.

        Returns:
            Dict[BranchFunc[Dict], Union[BaseOperator, str]]: A dictionary mapping branch functions to task names.
        """

        async def check_cache_true(input_value: Dict) -> bool:
            # Check if the cache contains the result for the given input
            if not input_value["model_cache_enable"]:
                return False
            cache_dict = _parse_cache_key_dict(input_value)
            cache_key: LLMCacheKey = self._client.new_key(**cache_dict)
            cache_value = await self._client.get(cache_key)
            logger.debug(
                f"cache_key: {cache_key}, hash key: {hash(cache_key)}, cache_value: {cache_value}"
            )
            await self.current_dag_context.save_to_share_data(
                _LLM_MODEL_INPUT_VALUE_KEY, cache_key
            )
            return True if cache_value else False

        async def check_cache_false(input_value: Dict):
            # Inverse of check_cache_true
            return not await check_cache_true(input_value)

        return {
            check_cache_true: self._cache_task_name,
            check_cache_false: self._model_task_name,
        }


class ModelStreamSaveCacheOperator(
    TransformStreamAbsOperator[ModelOutput, ModelOutput]
):
    """An operator to save the stream of model outputs to cache.

    Args:
        cache_manager (CacheManager): The cache manager for handling cache operations.
        **kwargs: Additional keyword arguments.
    """

    def __init__(self, cache_manager: CacheManager, **kwargs):
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)
        super().__init__(**kwargs)

    async def transform_stream(
        self, input_value: AsyncIterator[ModelOutput]
    ) -> AsyncIterator[ModelOutput]:
        """Transforms the input stream by saving the outputs to cache.

        Args:
            input_value (AsyncIterator[ModelOutput]): An asynchronous iterator of model outputs.

        Returns:
            AsyncIterator[ModelOutput]: The same input iterator, but the outputs are saved to cache.
        """
        llm_cache_key: LLMCacheKey = None
        outputs = []
        async for out in input_value:
            if not llm_cache_key:
                llm_cache_key = await self.current_dag_context.get_share_data(
                    _LLM_MODEL_INPUT_VALUE_KEY
                )
            outputs.append(out)
            yield out
        if llm_cache_key and _is_success_model_output(outputs):
            llm_cache_value: LLMCacheValue = self._client.new_value(output=outputs)
            await self._client.set(llm_cache_key, llm_cache_value)


class ModelSaveCacheOperator(MapOperator[ModelOutput, ModelOutput]):
    """An operator to save a single model output to cache.

    Args:
        cache_manager (CacheManager): The cache manager for handling cache operations.
        **kwargs: Additional keyword arguments.
    """

    def __init__(self, cache_manager: CacheManager, **kwargs):
        self._cache_manager = cache_manager
        self._client = LLMCacheClient(cache_manager)
        super().__init__(**kwargs)

    async def map(self, input_value: ModelOutput) -> ModelOutput:
        """Saves a single model output to cache and returns it.

        Args:
            input_value (ModelOutput): The output from the model to be cached.

        Returns:
            ModelOutput: The same input model output.
        """
        llm_cache_key: LLMCacheKey = await self.current_dag_context.get_share_data(
            _LLM_MODEL_INPUT_VALUE_KEY
        )
        llm_cache_value: LLMCacheValue = self._client.new_value(output=input_value)
        if llm_cache_key and _is_success_model_output(input_value):
            await self._client.set(llm_cache_key, llm_cache_value)
        return input_value


def _parse_cache_key_dict(input_value: Dict) -> Dict:
    """Parses and extracts relevant fields from input to form a cache key dictionary.

    Args:
        input_value (Dict): The input dictionary containing model and prompt parameters.

    Returns:
        Dict: A dictionary used for generating cache keys.
    """
    prompt: str = input_value.get("prompt")
    if prompt:
        prompt = prompt.strip()
    return {
        "prompt": prompt,
        "model_name": input_value.get("model"),
        "temperature": input_value.get("temperature"),
        "max_new_tokens": input_value.get("max_new_tokens"),
        "top_p": input_value.get("top_p", "1.0"),
        # TODO pass model_type
        "model_type": input_value.get("model_type", "huggingface"),
    }


def _is_success_model_output(out: Union[Dict, ModelOutput, List[ModelOutput]]) -> bool:
    if not out:
        return False
    if isinstance(out, list):
        # check last model output
        out = out[-1]
    error_code = 0
    if isinstance(out, ModelOutput):
        error_code = out.error_code
    else:
        error_code = int(out.get("error_code", 0))
    return error_code == 0
