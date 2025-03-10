import pytest

from .. import (
    DAG,
    InputOperator,
    WorkflowRunner,
)


def _register_dag_to_fastapi_app(dag):
    # TODO
    pass


@pytest.mark.asyncio
async def test_http_operator(runner: WorkflowRunner, stream_input_node: InputOperator):
    with DAG("test_map") as dag:
        pass
    _register_dag_to_fastapi_app(dag)
