from typing import AsyncIterator

import pytest

from dbgpt.core.awel import (
    DAG,
    InputSource,
    MapOperator,
    StreamifyAbsOperator,
    TransformStreamAbsOperator,
)
from dbgpt.core.awel.trigger.iterator_trigger import IteratorTrigger


class NumberProducerOperator(StreamifyAbsOperator[int, int]):
    """Create a stream of numbers from 0 to `n-1`"""

    async def streamify(self, n: int) -> AsyncIterator[int]:
        for i in range(n):
            yield i


class MyStreamingOperator(TransformStreamAbsOperator[int, int]):
    async def transform_stream(self, data: AsyncIterator[int]) -> AsyncIterator[int]:
        async for i in data:
            yield i * i


async def _check_stream_results(stream_results, expected_len):
    assert len(stream_results) == expected_len
    for _, result in stream_results:
        i = 0
        async for num in result:
            assert num == i * i
            i += 1


@pytest.mark.asyncio
async def test_single_data():
    with DAG("test_single_data"):
        trigger_task = IteratorTrigger(data=2)
        task = MapOperator(lambda x: x * x)
        trigger_task >> task
    results = await trigger_task.trigger()
    assert len(results) == 1
    assert results[0][1] == 4

    with DAG("test_single_data_stream"):
        trigger_task = IteratorTrigger(data=2, streaming_call=True)
        number_task = NumberProducerOperator()
        task = MyStreamingOperator()
        trigger_task >> number_task >> task
    stream_results = await trigger_task.trigger()
    await _check_stream_results(stream_results, 1)


@pytest.mark.asyncio
async def test_list_data():
    with DAG("test_list_data"):
        trigger_task = IteratorTrigger(data=[0, 1, 2, 3])
        task = MapOperator(lambda x: x * x)
        trigger_task >> task
    results = await trigger_task.trigger()
    assert len(results) == 4
    assert results == [(0, 0), (1, 1), (2, 4), (3, 9)]

    with DAG("test_list_data_stream"):
        trigger_task = IteratorTrigger(data=[0, 1, 2, 3], streaming_call=True)
        number_task = NumberProducerOperator()
        task = MyStreamingOperator()
        trigger_task >> number_task >> task
    stream_results = await trigger_task.trigger()
    await _check_stream_results(stream_results, 4)


@pytest.mark.asyncio
async def test_async_iterator_data():
    async def async_iter():
        for i in range(4):
            yield i

    with DAG("test_async_iterator_data"):
        trigger_task = IteratorTrigger(data=async_iter())
        task = MapOperator(lambda x: x * x)
        trigger_task >> task
    results = await trigger_task.trigger()
    assert len(results) == 4
    assert results == [(0, 0), (1, 1), (2, 4), (3, 9)]

    with DAG("test_async_iterator_data_stream"):
        trigger_task = IteratorTrigger(data=async_iter(), streaming_call=True)
        number_task = NumberProducerOperator()
        task = MyStreamingOperator()
        trigger_task >> number_task >> task
    stream_results = await trigger_task.trigger()
    await _check_stream_results(stream_results, 4)


@pytest.mark.asyncio
async def test_input_source_data():
    with DAG("test_input_source_data"):
        trigger_task = IteratorTrigger(data=InputSource.from_iterable([0, 1, 2, 3]))
        task = MapOperator(lambda x: x * x)
        trigger_task >> task
    results = await trigger_task.trigger()
    assert len(results) == 4
    assert results == [(0, 0), (1, 1), (2, 4), (3, 9)]

    with DAG("test_input_source_data_stream"):
        trigger_task = IteratorTrigger(
            data=InputSource.from_iterable([0, 1, 2, 3]),
            streaming_call=True,
        )
        number_task = NumberProducerOperator()
        task = MyStreamingOperator()
        trigger_task >> number_task >> task
    stream_results = await trigger_task.trigger()
    await _check_stream_results(stream_results, 4)


@pytest.mark.asyncio
async def test_parallel_safe():
    with DAG("test_parallel_safe"):
        trigger_task = IteratorTrigger(data=InputSource.from_iterable([0, 1, 2, 3]))
        task = MapOperator(lambda x: x * x)
        trigger_task >> task
    results = await trigger_task.trigger(parallel_num=3)
    assert len(results) == 4
    assert results == [(0, 0), (1, 1), (2, 4), (3, 9)]

    with DAG("test_input_source_data_stream"):
        trigger_task = IteratorTrigger(
            data=InputSource.from_iterable([0, 1, 2, 3]),
            streaming_call=True,
        )
        number_task = NumberProducerOperator()
        task = MyStreamingOperator()
        trigger_task >> number_task >> task
    stream_results = await trigger_task.trigger(parallel_num=3)
    await _check_stream_results(stream_results, 4)
