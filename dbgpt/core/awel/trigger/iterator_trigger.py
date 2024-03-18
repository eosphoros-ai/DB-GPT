"""Trigger for iterator data."""

import asyncio
from typing import Any, AsyncIterator, Iterator, List, Optional, Tuple, Union, cast

from ..operators.base import BaseOperator
from ..task.base import InputSource, TaskState
from ..task.task_impl import DefaultTaskContext, _is_async_iterator, _is_iterable
from .base import Trigger

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
    """Trigger for iterator data.

    Trigger the dag with iterator data.
    Return the list of results of the leaf nodes in the dag.
    The times of dag running is the length of the iterator data.
    """

    def __init__(
        self,
        data: IterDataType,
        parallel_num: int = 1,
        streaming_call: bool = False,
        show_progress: bool = True,
        **kwargs
    ):
        """Create a IteratorTrigger.

        Args:
            data (IterDataType): The iterator data.
            parallel_num (int, optional): The parallel number of the dag running.
                Defaults to 1.
            streaming_call (bool, optional): Whether the dag is a streaming call.
                Defaults to False.
        """
        self._iter_data = data
        self._parallel_num = parallel_num
        self._streaming_call = streaming_call
        self._show_progress = show_progress
        super().__init__(**kwargs)

    async def trigger(
        self, parallel_num: Optional[int] = None, **kwargs
    ) -> List[Tuple[Any, Any]]:
        """Trigger the dag with iterator data.

        If the dag is a streaming call, return the list of async iterator.

        Examples:
            .. code-block:: python

                import asyncio
                from dbgpt.core.awel import DAG, IteratorTrigger, MapOperator

                with DAG("test_dag") as dag:
                    trigger_task = IteratorTrigger([0, 1, 2, 3])
                    task = MapOperator(lambda x: x * x)
                    trigger_task >> task
                results = asyncio.run(trigger_task.trigger())
                # Fist element of the tuple is the input data, the second element is the
                # output data of the leaf node.
                assert results == [(0, 0), (1, 1), (2, 4), (3, 9)]

            .. code-block:: python

                import asyncio
                from datasets import Dataset
                from dbgpt.core.awel import (
                    DAG,
                    IteratorTrigger,
                    MapOperator,
                    InputSource,
                )

                data_samples = {
                    "question": ["What is 1+1?", "What is 7*7?"],
                    "answer": [2, 49],
                }
                dataset = Dataset.from_dict(data_samples)
                with DAG("test_dag_stream") as dag:
                    trigger_task = IteratorTrigger(InputSource.from_iterable(dataset))
                    task = MapOperator(lambda x: x["answer"])
                    trigger_task >> task
                results = asyncio.run(trigger_task.trigger())
                assert results == [
                    ({"question": "What is 1+1?", "answer": 2}, 2),
                    ({"question": "What is 7*7?", "answer": 49}, 49),
                ]
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

        async def call_stream(call_data: Any):
            async for out in await end_node.call_stream(call_data):
                yield out
            await dag._after_dag_end()

        async def run_node(call_data: Any) -> Tuple[Any, Any]:
            async with semaphore:
                if streaming_call:
                    task_output = call_stream(call_data)
                else:
                    task_output = await end_node.call(call_data)
                    await dag._after_dag_end()
                return call_data, task_output

        tasks = []

        if self._show_progress:
            from tqdm.asyncio import tqdm_asyncio

            async_module = tqdm_asyncio
        else:
            async_module = asyncio  # type: ignore

        async for data in _to_async_iterator(self._iter_data, task_id):
            tasks.append(run_node(data))
        results: List[Tuple[Any, Any]] = await async_module.gather(*tasks)
        return results
