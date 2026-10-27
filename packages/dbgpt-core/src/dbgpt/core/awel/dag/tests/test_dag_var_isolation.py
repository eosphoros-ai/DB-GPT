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
