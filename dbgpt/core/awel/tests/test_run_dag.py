import pytest
from typing import List
from .. import (
    DAG,
    WorkflowRunner,
    DAGContext,
    TaskState,
    InputOperator,
    MapOperator,
    JoinOperator,
    BranchOperator,
    ReduceStreamOperator,
    SimpleInputSource,
)
from .conftest import (
    runner,
    input_node,
    input_nodes,
    stream_input_node,
    stream_input_nodes,
    _is_async_iterator,
)


@pytest.mark.asyncio
async def test_input_node(runner: WorkflowRunner):
    input_node = InputOperator(SimpleInputSource("hello"))
    res: DAGContext[str] = await runner.execute_workflow(input_node)
    assert res.current_task_context.current_state == TaskState.SUCCESS
    assert res.current_task_context.task_output.output == "hello"

    async def new_steam_iter(n: int):
        for i in range(n):
            yield i

    num_iter = 10
    steam_input_node = InputOperator(SimpleInputSource(new_steam_iter(num_iter)))
    res: DAGContext[str] = await runner.execute_workflow(steam_input_node)
    assert res.current_task_context.current_state == TaskState.SUCCESS
    output_steam = res.current_task_context.task_output.output_stream
    assert output_steam
    assert _is_async_iterator(output_steam)
    i = 0
    async for x in output_steam:
        assert x == i
        i += 1


@pytest.mark.asyncio
async def test_map_node(runner: WorkflowRunner, stream_input_node: InputOperator):
    with DAG("test_map") as dag:
        map_node = MapOperator(lambda x: x * 2)
        stream_input_node >> map_node
        res: DAGContext[int] = await runner.execute_workflow(map_node)
        output_steam = res.current_task_context.task_output.output_stream
        assert output_steam
        i = 0
        async for x in output_steam:
            assert x == i * 2
            i += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stream_input_node, expect_sum",
    [
        ({"output_streams": [[0, 1, 2, 3]]}, 6),
        ({"output_streams": [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]}, 55),
    ],
    indirect=["stream_input_node"],
)
async def test_reduce_node(
    runner: WorkflowRunner, stream_input_node: InputOperator, expect_sum: int
):
    with DAG("test_reduce_node") as dag:
        reduce_node = ReduceStreamOperator(lambda x, y: x + y)
        stream_input_node >> reduce_node
        res: DAGContext[int] = await runner.execute_workflow(reduce_node)
        assert res.current_task_context.current_state == TaskState.SUCCESS
        assert not res.current_task_context.task_output.is_stream
        assert res.current_task_context.task_output.output == expect_sum


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_nodes",
    [
        ({"outputs": [0, 1, 2]}),
    ],
    indirect=["input_nodes"],
)
async def test_join_node(runner: WorkflowRunner, input_nodes: List[InputOperator]):
    def join_func(p1, p2, p3) -> int:
        return p1 + p2 + p3

    with DAG("test_join_node") as dag:
        join_node = JoinOperator(join_func)
        for input_node in input_nodes:
            input_node >> join_node
        res: DAGContext[int] = await runner.execute_workflow(join_node)
        assert res.current_task_context.current_state == TaskState.SUCCESS
        assert not res.current_task_context.task_output.is_stream
        assert res.current_task_context.task_output.output == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_node, is_odd",
    [
        ({"outputs": [0]}, False),
        ({"outputs": [1]}, True),
    ],
    indirect=["input_node"],
)
async def test_branch_node(
    runner: WorkflowRunner, input_node: InputOperator, is_odd: bool
):
    def join_func(o1, o2) -> int:
        print(f"join func result, o1: {o1}, o2: {o2}")
        return o1 or o2

    with DAG("test_join_node") as dag:
        odd_node = MapOperator(
            lambda x: 999, task_id="odd_node", task_name="odd_node_name"
        )
        even_node = MapOperator(
            lambda x: 888, task_id="even_node", task_name="even_node_name"
        )
        join_node = JoinOperator(join_func)
        branch_node = BranchOperator(
            {lambda x: x % 2 == 1: odd_node, lambda x: x % 2 == 0: even_node}
        )
        branch_node >> odd_node >> join_node
        branch_node >> even_node >> join_node

        input_node >> branch_node

        res: DAGContext[int] = await runner.execute_workflow(join_node)
        assert res.current_task_context.current_state == TaskState.SUCCESS
        expect_res = 999 if is_odd else 888
        assert res.current_task_context.task_output.output == expect_res
