"""Execution tests for explicitly grouped, independent operators."""

import asyncio

import pytest

from .. import DAG, JoinOperator, MapOperator
from ..runner.local_runner import DefaultWorkflowRunner


@pytest.mark.asyncio
async def test_parallel_contexts_join_and_shared_ancestor():
    started = set()
    both_started = asyncio.Event()
    root_calls = []

    async def root(value):
        root_calls.append(value)
        return value

    class Worker(MapOperator):
        parallel_group = "analysis"

        async def map(self, value):
            context = self.current_dag_context
            task_id = context.current_task_context.task_id
            started.add(self.node_name)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 1)
            # A sibling must not overwrite this operator's active context.
            assert context.current_task_context.task_id == task_id == self.node_id
            await context.save_to_share_data(self.node_name, value)
            return self.node_name

    with DAG("parallel_join"):
        source = MapOperator(root)
        a = Worker(task_name="trend")
        b = Worker(task_name="quality")
        join = JoinOperator(lambda *values: list(values))
        source >> a >> join
        source >> b >> join
    result = await DefaultWorkflowRunner().execute_workflow(
        join, call_data={"data": "scope"}
    )
    assert root_calls == ["scope"]
    assert result.current_task_context.task_output.output == ["trend", "quality"]
    assert await result.get_from_share_data("trend") == "scope"
    assert await result.get_from_share_data("quality") == "scope"


@pytest.mark.asyncio
async def test_parallel_failure_cancels_sibling_and_does_not_run_join():
    sibling_started = asyncio.Event()
    cancelled = asyncio.Event()
    joined = []

    async def fail(value):
        await sibling_started.wait()
        raise ValueError("quality failed")

    async def sibling(value):
        sibling_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with DAG("parallel_failure"):
        source = MapOperator(lambda value: value)
        a = MapOperator(fail)
        b = MapOperator(sibling)
        a.parallel_group = b.parallel_group = "analysis"
        join = JoinOperator(lambda *values: joined.append(values))
        source >> a >> join
        source >> b >> join
    with pytest.raises(ValueError, match="quality failed"):
        await asyncio.wait_for(
            DefaultWorkflowRunner().execute_workflow(join, call_data={"data": "scope"}),
            2,
        )
    assert cancelled.is_set()
    assert joined == []


@pytest.mark.asyncio
async def test_parallel_caller_cancellation_stops_all_workers():
    started = set()
    cancelled = set()
    both_started = asyncio.Event()

    def worker(name):
        async def run(value):
            started.add(name)
            if len(started) == 2:
                both_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.add(name)

        return run

    with DAG("parallel_cancel"):
        source = MapOperator(lambda value: value)
        a = MapOperator(worker("a"))
        b = MapOperator(worker("b"))
        a.parallel_group = b.parallel_group = "analysis"
        join = JoinOperator(lambda *values: values)
        source >> a >> join
        source >> b >> join
    task = asyncio.create_task(
        DefaultWorkflowRunner().execute_workflow(join, call_data={"data": "scope"})
    )
    await asyncio.wait_for(both_started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled == {"a", "b"}


@pytest.mark.asyncio
async def test_group_concurrency_is_bounded_to_two():
    active = 0
    peak = 0

    async def worker(value):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return value

    with DAG("parallel_limit"):
        source = MapOperator(lambda value: value)
        workers = [MapOperator(worker) for _ in range(5)]
        join = JoinOperator(lambda *values: values)
        for node in workers:
            node.parallel_group = "analysis"
            source >> node >> join
    result = await DefaultWorkflowRunner().execute_workflow(
        join, call_data={"data": "scope"}
    )
    assert peak == 2
    assert len(result.current_task_context.task_output.output) == 5


@pytest.mark.asyncio
async def test_ungrouped_branches_remain_sequential():
    events = []

    def worker(name):
        async def run(value):
            events.append(f"{name}:start")
            await asyncio.sleep(0)
            events.append(f"{name}:end")
            return name

        return run

    with DAG("serial_compatibility"):
        source = MapOperator(lambda value: value)
        a = MapOperator(worker("a"))
        b = MapOperator(worker("b"))
        join = JoinOperator(lambda *values: values)
        source >> a >> join
        source >> b >> join
    await DefaultWorkflowRunner().execute_workflow(join, call_data={"data": "scope"})
    assert events == ["a:start", "a:end", "b:start", "b:end"]
