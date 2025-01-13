from contextlib import asynccontextmanager

import pytest
import pytest_asyncio

from ...interface.variables import (
    StorageVariables,
    StorageVariablesProvider,
    VariablesIdentifier,
    VariablesPlaceHolder,
)
from .. import DAG, DAGVar, InputOperator, MapOperator, SimpleInputSource


class VariablesOperator(MapOperator[str, str]):
    def __init__(self, int_var: int, str_var: str, secret: str, **kwargs):
        super().__init__(**kwargs)
        self._int_var = int_var
        self._str_var = str_var
        self._secret = secret

    async def map(self, x: str) -> str:
        return (
            f"x: {x}, int_var: {self._int_var}, str_var: {self._str_var}, "
            f"secret: {self._secret}"
        )


@pytest.fixture
def default_dag():
    with DAG("test_dag") as dag:
        input_node = InputOperator(input_source=SimpleInputSource.from_callable())
        map_node = MapOperator(lambda x: x * 2)
        input_node >> map_node
        return dag


@asynccontextmanager
async def _create_variables(**kwargs):
    variables_provider = StorageVariablesProvider()
    DAGVar.set_variables_provider(variables_provider)

    vars = kwargs.get("vars")
    variables = {}
    if vars and isinstance(vars, dict):
        for param_key, param_var in vars.items():
            key = param_var.get("key")
            value = param_var.get("value")
            value_type = param_var.get("value_type")
            category = param_var.get("category", "common")
            id = VariablesIdentifier.from_str_identifier(key)
            variables_provider.save(
                StorageVariables.from_identifier(
                    id, value, value_type, label="", category=category
                )
            )
            variables[param_key] = VariablesPlaceHolder(param_key, key)
    else:
        raise ValueError("vars is required.")

    with DAG("simple_dag") as _dag:
        map_node = VariablesOperator(**variables)
        yield map_node


@pytest_asyncio.fixture
async def variables_node(request):
    param = getattr(request, "param", {})
    async with _create_variables(**param) as node:
        yield node


@pytest.mark.asyncio
async def test_default_dag(default_dag: DAG):
    leaf_node = default_dag.leaf_nodes[0]
    res = await leaf_node.call(2)
    assert res == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "variables_node",
    [
        (
            {
                "vars": {
                    "int_var": {
                        "key": "${int_key:my_int_var@global}",
                        "value": 0,
                        "value_type": "int",
                    },
                    "str_var": {
                        "key": "${str_key:my_str_var@global}",
                        "value": "1",
                        "value_type": "str",
                    },
                    "secret": {
                        "key": "${secret_key:my_secret_var@global}",
                        "value": "2131sdsdf",
                        "value_type": "str",
                        "category": "secret",
                    },
                }
            }
        ),
    ],
    indirect=["variables_node"],
)
async def test_input_nodes(variables_node: VariablesOperator):
    res = await variables_node.call("test")
    assert res == "x: test, int_var: 0, str_var: 1, secret: 2131sdsdf"
