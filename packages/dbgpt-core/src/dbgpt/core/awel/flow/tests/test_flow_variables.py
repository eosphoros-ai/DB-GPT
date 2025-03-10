import json
from typing import cast

import pytest

from dbgpt.configs import VARIABLES_SCOPE_FLOW_PRIVATE
from dbgpt.core.awel import BaseOperator, DAGVar, MapOperator
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    Parameter,
    VariablesDynamicOptions,
    ViewMetadata,
    ui,
)
from dbgpt.core.awel.flow.flow_factory import (
    FlowData,
    FlowFactory,
    FlowPanel,
    FlowVariables,
)


class MyVariablesOperator(MapOperator[str, str]):
    metadata = ViewMetadata(
        label="My Test Variables Operator",
        name="my_test_variables_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a variables option.",
        parameters=[
            Parameter.build_from(
                "OpenAI API Key",
                "openai_api_key",
                type=str,
                placeholder="Please select the OpenAI API key",
                description="The OpenAI API key to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIPasswordInput(
                    key="dbgpt.model.openai.api_key",
                ),
            ),
            Parameter.build_from(
                "Model",
                "model",
                type=str,
                placeholder="Please select the model",
                description="The model to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key="dbgpt.model.openai.model",
                ),
            ),
            Parameter.build_from(
                "DAG Var 1",
                "dag_var1",
                type=str,
                placeholder="Please select the DAG variable 1",
                description="The DAG variable 1.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key="dbgpt.core.flow.params", scope=VARIABLES_SCOPE_FLOW_PRIVATE
                ),
            ),
            Parameter.build_from(
                "DAG Var 2",
                "dag_var2",
                type=str,
                placeholder="Please select the DAG variable 2",
                description="The DAG variable 2.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key="dbgpt.core.flow.params", scope=VARIABLES_SCOPE_FLOW_PRIVATE
                ),
            ),
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Model info",
                "model",
                str,
                description="The model info.",
            ),
        ],
    )

    def __init__(
        self, openai_api_key: str, model: str, dag_var1: str, dag_var2: str, **kwargs
    ):
        super().__init__(**kwargs)
        self._openai_api_key = openai_api_key
        self._model = model
        self._dag_var1 = dag_var1
        self._dag_var2 = dag_var2

    async def map(self, user_name: str) -> str:
        dict_dict = {
            "openai_api_key": self._openai_api_key,
            "model": self._model,
            "dag_var1": self._dag_var1,
            "dag_var2": self._dag_var2,
        }
        json_data = json.dumps(dict_dict, ensure_ascii=False)
        return "Your name is %s, and your model info is %s." % (user_name, json_data)


class EndOperator(MapOperator[str, str]):
    metadata = ViewMetadata(
        label="End Operator",
        name="end_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that ends the flow.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Input",
                "input",
                str,
                description="The input to the end operator.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Output",
                "output",
                str,
                description="The output of the end operator.",
            ),
        ],
    )

    async def map(self, input: str) -> str:
        return f"End operator received input: {input}"


@pytest.fixture
def json_flow():
    operators = [MyVariablesOperator, EndOperator]
    metadata_list = [operator.metadata.to_dict() for operator in operators]
    node_names = {}
    name_to_parameters_dict = {
        "my_test_variables_operator": {
            "openai_api_key": "${dbgpt.model.openai.api_key:my_key@global}",
            "model": "${dbgpt.model.openai.model:default_model@global}",
            "dag_var1": "${dbgpt.core.flow.params:name1@%s}"
            % VARIABLES_SCOPE_FLOW_PRIVATE,
            "dag_var2": "${dbgpt.core.flow.params:name2@%s}"
            % VARIABLES_SCOPE_FLOW_PRIVATE,
        }
    }
    name_to_metadata_dict = {metadata["name"]: metadata for metadata in metadata_list}
    ui_nodes = []
    for metadata in metadata_list:
        type_name = metadata["type_name"]
        name = metadata["name"]
        id = metadata["id"]
        if type_name in node_names:
            raise ValueError(f"Duplicate node type name: {type_name}")
        # Replace id to flow data id.
        metadata["id"] = f"{id}_0"
        parameters = metadata["parameters"]
        parameters_dict = name_to_parameters_dict.get(name, {})
        for parameter in parameters:
            parameter_name = parameter["name"]
            if parameter_name in parameters_dict:
                parameter["value"] = parameters_dict[parameter_name]
        ui_nodes.append(
            {
                "width": 288,
                "height": 352,
                "id": metadata["id"],
                "position": {
                    "x": -149.98120112708142,
                    "y": 666.9468497341901,
                    "zoom": 0.0,
                },
                "type": "customNode",
                "position_absolute": {
                    "x": -149.98120112708142,
                    "y": 666.9468497341901,
                    "zoom": 0.0,
                },
                "data": metadata,
            }
        )

    ui_edges = []
    source_id = name_to_metadata_dict["my_test_variables_operator"]["id"]
    target_id = name_to_metadata_dict["end_operator"]["id"]
    ui_edges.append(
        {
            "source": source_id,
            "target": target_id,
            "source_order": 0,
            "target_order": 0,
            "id": f"{source_id}|{target_id}",
            "source_handle": f"{source_id}|outputs|0",
            "target_handle": f"{target_id}|inputs|0",
            "type": "buttonedge",
        }
    )
    return {
        "nodes": ui_nodes,
        "edges": ui_edges,
        "viewport": {
            "x": 509.2191773722104,
            "y": -66.11286175905718,
            "zoom": 1.252741002590748,
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "variables_provider",
    [
        (
            {
                "vars": {
                    "openai_api_key": {
                        "key": "${dbgpt.model.openai.api_key:my_key@global}",
                        "value": "my_openai_api_key",
                        "value_type": "str",
                        "category": "secret",
                    },
                    "model": {
                        "key": "${dbgpt.model.openai.model:default_model@global}",
                        "value": "GPT-4o",
                        "value_type": "str",
                    },
                }
            }
        ),
    ],
    indirect=["variables_provider"],
)
@pytest.fixture
def variables_provider():
    from dbgpt_serve.flow.api.variables_provider import BuiltinFlowVariablesProvider

    provider = BuiltinFlowVariablesProvider()
    yield provider


async def test_build_flow(json_flow, variables_provider):
    DAGVar.set_variables_provider(variables_provider)
    flow_data = FlowData(**json_flow)
    variables = [
        FlowVariables(
            key="dbgpt.core.flow.params",
            name="name1",
            label="Name 1",
            value="value1",
            value_type="str",
            category="common",
            scope=VARIABLES_SCOPE_FLOW_PRIVATE,
            # scope_key="my_test_flow",
        ),
        FlowVariables(
            key="dbgpt.core.flow.params",
            name="name2",
            label="Name 2",
            value="value2",
            value_type="str",
            category="common",
            scope=VARIABLES_SCOPE_FLOW_PRIVATE,
            # scope_key="my_test_flow",
        ),
    ]
    flow_panel = FlowPanel(
        label="My Test Flow",
        name="my_test_flow",
        flow_data=flow_data,
        state="deployed",
        variables=variables,
    )
    factory = FlowFactory()
    dag = factory.build(flow_panel)

    leaf_node: BaseOperator = cast(BaseOperator, dag.leaf_nodes[0])
    result = await leaf_node.call("Alice")
    expected_dict = {
        "openai_api_key": "my_openai_api_key",
        "model": "GPT-4o",
        "dag_var1": "value1",
        "dag_var2": "value2",
    }
    expected_dict_str = json.dumps(expected_dict, ensure_ascii=False)
    assert (
        result
        == f"End operator received input: Your name is Alice, and your model info is "
        f"{expected_dict_str}."
    )
