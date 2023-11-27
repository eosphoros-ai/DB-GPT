import pytest
import pytest_asyncio
from typing import AsyncIterator, List
from contextlib import contextmanager, asynccontextmanager
from .. import (
    WorkflowRunner,
    InputOperator,
    DAGContext,
    TaskState,
    DefaultWorkflowRunner,
    SimpleInputSource,
)
from ..task.task_impl import _is_async_iterator


@pytest.fixture
def runner():
    return DefaultWorkflowRunner()


def _create_stream(num_nodes) -> List[AsyncIterator[int]]:
    iters = []
    for _ in range(num_nodes):

        async def stream_iter():
            for i in range(10):
                yield i

        stream_iter = stream_iter()
        assert _is_async_iterator(stream_iter)
        iters.append(stream_iter)
    return iters


def _create_stream_from(output_streams: List[List[int]]) -> List[AsyncIterator[int]]:
    iters = []
    for single_stream in output_streams:

        async def stream_iter():
            for i in single_stream:
                yield i

        stream_iter = stream_iter()
        assert _is_async_iterator(stream_iter)
        iters.append(stream_iter)
    return iters


@asynccontextmanager
async def _create_input_node(**kwargs):
    num_nodes = kwargs.get("num_nodes")
    is_stream = kwargs.get("is_stream", False)
    if is_stream:
        outputs = kwargs.get("output_streams")
        if outputs:
            if num_nodes and num_nodes != len(outputs):
                raise ValueError(
                    f"num_nodes {num_nodes} != the length of output_streams {len(outputs)}"
                )
            outputs = _create_stream_from(outputs)
        else:
            num_nodes = num_nodes or 1
            outputs = _create_stream(num_nodes)
    else:
        outputs = kwargs.get("outputs", ["Hello."])
    nodes = []
    for output in outputs:
        print(f"output: {output}")
        input_source = SimpleInputSource(output)
        input_node = InputOperator(input_source)
        nodes.append(input_node)
    yield nodes


@pytest_asyncio.fixture
async def input_node(request):
    param = getattr(request, "param", {})
    async with _create_input_node(**param) as input_nodes:
        yield input_nodes[0]


@pytest_asyncio.fixture
async def stream_input_node(request):
    param = getattr(request, "param", {})
    param["is_stream"] = True
    async with _create_input_node(**param) as input_nodes:
        yield input_nodes[0]


@pytest_asyncio.fixture
async def input_nodes(request):
    param = getattr(request, "param", {})
    async with _create_input_node(**param) as input_nodes:
        yield input_nodes


@pytest_asyncio.fixture
async def stream_input_nodes(request):
    param = getattr(request, "param", {})
    param["is_stream"] = True
    async with _create_input_node(**param) as input_nodes:
        yield input_nodes
