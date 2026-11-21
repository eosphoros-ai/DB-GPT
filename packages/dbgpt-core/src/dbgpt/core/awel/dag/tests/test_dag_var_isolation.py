"""DAG context isolation for concurrent AWEL tasks.

``DAGVar`` keeps the async DAG stack in a ``ContextVar`` whose *default* is a
single ``deque`` object created once at import time
(``base.py:140``). ``enter_dag`` reads that value, appends to it in place and
only then calls ``set()`` (``base.py:159-162``), so every task that starts
before any task has called ``set()`` reads -- and mutates -- the same shared
deque. Two DAGs built concurrently therefore see each other's stack, and
``exit_dag`` pops the entry that belongs to the other task.
"""

import asyncio

import pytest

from ..base import DAG, DAGVar


@pytest.mark.asyncio
async def test_concurrent_dag_stacks_stay_isolated_between_tasks():
    """Each task must see only the DAG it entered itself."""
    dag1 = DAG("dag1")
    dag2 = DAG("dag2")

    entered1, entered2 = asyncio.Event(), asyncio.Event()
    read1, read2 = asyncio.Event(), asyncio.Event()
    observed: dict = {}

    async def worker(name, dag, own_entered, other_entered, own_read, other_read):
        DAGVar.enter_dag(dag)
        own_entered.set()
        # Both tasks are inside their ``with dag`` region from here on.
        await other_entered.wait()
        observed[name] = DAGVar.get_current_dag()
        own_read.set()
        # Do not let the first task pop the second task's entry.
        await other_read.wait()
        DAGVar.exit_dag()

    await asyncio.gather(
        worker("first", dag1, entered1, entered2, read1, read2),
        worker("second", dag2, entered2, entered1, read2, read1),
    )

    assert observed["first"] is dag1
    assert observed["second"] is dag2


@pytest.mark.asyncio
async def test_task_without_a_dag_does_not_observe_another_task_s_dag():
    """A caller that never entered a DAG must not see a DAG at all."""
    dag = DAG("holder")
    entered, release = asyncio.Event(), asyncio.Event()

    async def holder():
        DAGVar.enter_dag(dag)
        entered.set()
        await release.wait()
        DAGVar.exit_dag()

    task = asyncio.create_task(holder())
    await entered.wait()

    assert DAGVar.get_current_dag() is None

    release.set()
    await task


@pytest.mark.asyncio
async def test_child_task_retains_inherited_dag_after_parent_exits():
    """A task created inside a DAG keeps that DAG when the parent leaves it.

    ``asyncio`` copies the current context into the child task, so the child
    inherits the stack as it was at creation time. Entering the stack in place
    (the pre-fix behaviour) made the parent's ``exit_dag`` pop the very deque
    the child reads, so the child saw no DAG at all. Copying before mutating is
    what keeps the inherited stack intact.
    """
    dag = DAG("parent")
    child_ready = asyncio.Event()
    release_child = asyncio.Event()

    async def child():
        child_ready.set()
        await release_child.wait()
        return DAGVar.get_current_dag()

    DAGVar.enter_dag(dag)
    try:
        task = asyncio.create_task(child())
        await child_ready.wait()
        DAGVar.exit_dag()

        release_child.set()
        assert await task is dag, (
            "the child task lost the DAG it inherited when the parent exited"
        )
    finally:
        if DAGVar.get_current_dag() is not None:
            DAGVar.exit_dag()
