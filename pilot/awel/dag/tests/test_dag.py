import pytest
import threading
import asyncio
from ..dag import DAG, DAGContext


def test_dag_context_sync():
    dag1 = DAG("dag1")
    dag2 = DAG("dag2")

    with dag1:
        assert DAGContext.get_current_dag() == dag1
        with dag2:
            assert DAGContext.get_current_dag() == dag2
        assert DAGContext.get_current_dag() == dag1
    assert DAGContext.get_current_dag() is None


def test_dag_context_threading():
    def thread_function(dag):
        DAGContext.enter_dag(dag)
        assert DAGContext.get_current_dag() == dag
        DAGContext.exit_dag()

    dag1 = DAG("dag1")
    dag2 = DAG("dag2")

    thread1 = threading.Thread(target=thread_function, args=(dag1,))
    thread2 = threading.Thread(target=thread_function, args=(dag2,))

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    assert DAGContext.get_current_dag() is None


@pytest.mark.asyncio
async def test_dag_context_async():
    async def async_function(dag):
        DAGContext.enter_dag(dag)
        assert DAGContext.get_current_dag() == dag
        DAGContext.exit_dag()

    dag1 = DAG("dag1")
    dag2 = DAG("dag2")

    await asyncio.gather(async_function(dag1), async_function(dag2))

    assert DAGContext.get_current_dag() is None
