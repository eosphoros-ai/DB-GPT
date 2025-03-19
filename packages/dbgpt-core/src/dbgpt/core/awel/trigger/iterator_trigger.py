"""Trigger for iterator data with caching support."""

import asyncio
import logging
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from ..operators.base import BaseOperator
from ..task.base import InputSource, TaskState
from ..task.task_impl import DefaultTaskContext, _is_async_iterator, _is_iterable
from ..util.cache_util import CacheStorage, stream_from_cached_data
from .base import Trigger

logger = logging.getLogger(__name__)
IterDataType = Union[InputSource, Iterator, AsyncIterator, Any]


async def _to_async_iterator(iter_data: IterDataType, task_id: str) -> AsyncIterator:
    """Convert iter_data to an async iterator."""
    if _is_async_iterator(iter_data):
        async for item in iter_data:  # type: ignore
            yield item
    elif _is_iterable(iter_data):
        for item in iter_data:  # type: ignore
            yield item
    elif isinstance(iter_data, InputSource):
        task_ctx: DefaultTaskContext[Any] = DefaultTaskContext(
            task_id, TaskState.RUNNING, None
        )
        data = await iter_data.read(task_ctx)
        if data.is_stream:
            async for item in data.output_stream:
                yield item
        else:
            yield data.output
    else:
        yield iter_data


class IteratorTrigger(Trigger[List[Tuple[Any, Any]]]):
    """Trigger for iterator data with caching support.

    Trigger the dag with iterator data.
    Return the list of results of the leaf nodes in the dag.
    The times of dag running is the length of the iterator data.

    Supports caching of results to avoid redundant computation.
    """

    def __init__(
        self,
        data: IterDataType,
        parallel_num: int = 1,
        streaming_call: bool = False,
        show_progress: bool = True,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        # New caching parameters
        cache_storage: Optional[CacheStorage] = None,
        cache_key_fn: Optional[Callable[[Any], str]] = None,
        cache_ttl: Optional[int] = None,
        cache_enabled: bool = False,
        **kwargs,
    ):
        """Create a IteratorTrigger.

        Args:
            data (IterDataType): The iterator data.
            parallel_num (int, optional): The parallel number of the dag running.
                Defaults to 1.
            streaming_call (bool, optional): Whether the dag is a streaming call.
                Defaults to False.
            show_progress (bool, optional): Whether to show progress bar.
                Defaults to True.
            max_retries (int, optional): Maximum retry attempts for non-streaming calls.
                Defaults to 0 (no retries).
            retry_delay (float, optional): Delay between retries in seconds.
                Defaults to 1.0.
            timeout (Optional[float], optional): Timeout per task in seconds.
                Defaults to None (no timeout).
            cache_storage (Optional[CacheStorage], optional): Storage interface for
                caching.  Defaults to None.
            cache_key_fn (Optional[Callable[[Any], str]], optional): Function to
                calculate cache key from input data. Defaults to None.
            cache_ttl (Optional[int], optional): Time-to-live for cached items in
                seconds. Defaults to None (no expiration).
            cache_enabled (bool, optional): Whether to enable caching.
                Defaults to False.
        """
        self._iter_data = data
        self._parallel_num = parallel_num
        self._streaming_call = streaming_call
        self._show_progress = show_progress
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._timeout = timeout

        # Cache-related attributes
        self._cache_enabled = cache_enabled
        self._cache_storage = cache_storage
        self._cache_key_fn = cache_key_fn
        self._cache_ttl = cache_ttl

        super().__init__(**kwargs)

    async def _get_cache_key(self, data: Any) -> Optional[str]:
        """Generate cache key for the given data if caching is enabled.

        Returns None if caching is disabled or no key function is provided.
        """
        if not self._cache_enabled or not self._cache_storage or not self._cache_key_fn:
            return None

        try:
            return self._cache_key_fn(data)
        except Exception as e:
            logger.warning(f"Failed to generate cache key: {str(e)}")
            return None

    async def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached result if available."""
        if not self._cache_storage:
            return None

        try:
            if await self._cache_storage.exists(cache_key):
                return await self._cache_storage.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache retrieval error for key {cache_key}: {str(e)}")

        return None

    async def _store_in_cache(self, cache_key: str, result: Any) -> None:
        """Store result in cache."""
        if not self._cache_storage:
            return

        try:
            await self._cache_storage.set(cache_key, result, self._cache_ttl)
        except Exception as e:
            logger.warning(f"Cache storage error for key {cache_key}: {str(e)}")

    async def trigger(
        self, parallel_num: Optional[int] = None, **kwargs
    ) -> List[Tuple[Any, Any]]:
        """Trigger the dag with iterator data, with optional caching.

        If the dag is a streaming call, return the list of async iterator.

        Examples:
            .. code-block:: python

                import asyncio
                from dbgpt.core.awel import DAG, IteratorTrigger, MapOperator


                # Define a cache key function
                def cache_key_fn(data):
                    return f"calculation_{data}"


                # Create a memory cache
                cache = MemoryCacheStorage()

                with DAG("test_dag") as dag:
                    trigger_task = IteratorTrigger(
                        [0, 1, 2, 3],
                        cache_storage=cache,
                        cache_key_fn=cache_key_fn,
                        cache_enabled=True,
                    )
                    task = MapOperator(lambda x: x * x)
                    trigger_task >> task
                results = asyncio.run(trigger_task.trigger())
                # First element of the tuple is the input data, the second element is
                # the output data of the leaf node.
                assert results == [(0, 0), (1, 1), (2, 4), (3, 9)]

        Args:
            parallel_num (Optional[int], optional): The parallel number of the dag
                running. Defaults to None.

        Returns:
            List[Tuple[Any, Any]]: The list of results of the leaf nodes in the dag.
                The first element of the tuple is the input data, the second element is
                the output data of the leaf node.
        """
        dag = self.dag
        if not dag:
            raise ValueError("DAG is not set for IteratorTrigger")
        leaf_nodes = dag.leaf_nodes
        if len(leaf_nodes) != 1:
            raise ValueError("IteratorTrigger just support one leaf node in dag")
        end_node = cast(BaseOperator, leaf_nodes[0])
        streaming_call = self._streaming_call
        semaphore = asyncio.Semaphore(parallel_num or self._parallel_num)
        task_id = self.node_id
        max_retries = self._max_retries

        async def call_stream(call_data: Any, cache_key: Optional[str] = None):
            """Process streaming data with optional caching."""
            # If caching is enabled and we have a cache key, try to get cached results
            if cache_key is not None:
                cached_result = await self._get_cached_result(cache_key)
                if cached_result is not None:
                    # For streaming cached results, we need to yield each item
                    for item in cached_result:
                        yield item
                    return

            # Store results for caching if needed
            cached_items = []
            try:
                async for out in await end_node.call_stream(call_data):
                    # Store the result for caching
                    if cache_key is not None:
                        cached_items.append(out)
                    yield out
            finally:
                # Cache the collection of results after processing is complete
                if cache_key is not None and cached_items:
                    await self._store_in_cache(cache_key, cached_items)
                await dag._after_dag_end(end_node.current_event_loop_task_id)

        async def run_node_with_control(call_data: Any) -> Tuple[Any, Any]:
            async with semaphore:
                # Generate cache key if caching is enabled
                cache_key = await self._get_cache_key(call_data)

                if streaming_call:
                    # Streaming calls
                    if self._timeout:
                        stream_generator = call_stream(call_data, cache_key)
                        task_output = await asyncio.wait_for(
                            anext(stream_generator.__aiter__()), timeout=self._timeout
                        )

                        # Create a combined generator that includes the first item and
                        # the rest
                        async def combined_generator():
                            yield task_output
                            async for item in stream_generator:
                                yield item

                        return call_data, combined_generator()
                    else:
                        return call_data, call_stream(call_data, cache_key)

                # Non-streaming call with cache and retry logic
                # Try to get from cache first if caching is enabled
                if cache_key is not None:
                    cached_result = await self._get_cached_result(cache_key)
                    if cached_result is not None:
                        logger.info(f"Cache hit for key {cache_key}")
                        # For non-streaming calls, just return the cached result
                        # directly
                        # For streaming calls that were previously cached, recreate the
                        # stream
                        if isinstance(cached_result, list) and self._streaming_call:
                            return call_data, stream_from_cached_data(cached_result)
                        return call_data, cached_result

                # If not cached or cache miss, proceed with regular execution
                nonlocal max_retries
                attempts = 0
                while True:
                    try:
                        if self._timeout:
                            task_output = await asyncio.wait_for(
                                end_node.call(call_data), timeout=self._timeout
                            )
                        else:
                            task_output = await end_node.call(call_data)

                        # Cache the result if caching is enabled
                        if cache_key is not None:
                            await self._store_in_cache(cache_key, task_output)

                        return call_data, task_output
                    except (Exception, asyncio.TimeoutError) as e:
                        attempts += 1
                        if attempts > max_retries:
                            raise RuntimeError(
                                f"Failed after {max_retries} retries: {str(e)}"
                            ) from e
                        await asyncio.sleep(self._retry_delay)
                        logger.warning(
                            f"Failed attempt {attempts}/{max_retries} for task "
                            f"{end_node.node_id}: {str(e)}"
                        )

        tasks = []

        if self._show_progress:
            from tqdm.asyncio import tqdm_asyncio

            async_module = tqdm_asyncio
        else:
            async_module = asyncio  # type: ignore

        async for data in _to_async_iterator(self._iter_data, task_id):
            tasks.append(run_node_with_control(data))
        results: List[Tuple[Any, Any]] = await async_module.gather(*tasks)
        return results
