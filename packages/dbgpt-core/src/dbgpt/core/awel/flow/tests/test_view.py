import pytest

from dbgpt.core.awel.operators.common_operator import MapOperator

from ..base import IOField, Parameter, ResourceMetadata, ViewMetadata, register_resource


def test_show_metadata():
    class MyMapOperator(MapOperator[int, int]):
        metadata = ViewMetadata(
            label="MyMapOperator",
            name="MyMapOperator",
            category="llm",
            description="MyMapOperator",
            parameters=[],
            inputs=[
                IOField.build_from(
                    "Input", "input", int, description="The input of the map function."
                )
            ],
            outputs=[
                IOField.build_from("Output", "output", int, description="The output.")
            ],
        )

    metadata = MyMapOperator.metadata
    dict_data = metadata.to_dict()
    view_data = ViewMetadata(**dict_data)
    new_task = MyMapOperator.build_from(view_data)
    assert new_task.metadata == metadata


@pytest.mark.asyncio
async def test_create_with_params():
    class MyPowOperator(MapOperator[int, int]):
        metadata = ViewMetadata(
            label="Pow Operator",
            name="my_pow_operator",
            category="common",
            description="Calculate the power of the input.",
            parameters=[
                Parameter.build_from(
                    "Exponent",
                    "exponent",
                    int,
                    default=2,
                    description="The exponent of the pow.",
                ),
            ],
            inputs=[
                IOField.build_from(
                    "Input Number",
                    "input_number",
                    int,
                    description="The number to calculate the power.",
                ),
            ],
            outputs=[
                IOField.build_from(
                    "Output", "output", int, description="The output of the pow."
                ),
            ],
        )

        def __init__(self, exponent: int, **kwargs):
            super().__init__(**kwargs)
            self._exp = exponent

        async def map(self, input_number: int) -> int:
            return pow(input_number, self._exp)

    metadata = MyPowOperator.metadata
    dict_data = metadata.to_dict()
    dict_data["parameters"][0]["value"] = 3
    view_metadata = ViewMetadata(**dict_data)
    new_task = MyPowOperator.build_from(view_metadata)
    assert new_task is not None
    assert new_task._exp == 3
    assert await new_task.call(2) == 8


@pytest.mark.asyncio
async def test_create_with_resource():
    class LLMClient:
        pass

    @register_resource(
        label="MyLLMClient",
        name="my_llm_client",
        category="llm_client",
        description="Client for LLM.",
        parameters=[
            Parameter.build_from(label="The API Key", name="api_key", type=str)
        ],
    )
    class MyLLMClient(LLMClient):
        def __init__(self, api_key: str):
            self._api_key = api_key

    class MyLLMOperator(MapOperator[str, str]):
        metadata = ViewMetadata(
            label="MyLLMOperator",
            name="my_llm_operator",
            category="llm",
            description="MyLLMOperator",
            parameters=[
                Parameter.build_from(
                    "LLM Client",
                    "llm_client",
                    LLMClient,
                    description="The LLM Client.",
                ),
            ],
            inputs=[
                IOField.build_from(
                    "Input",
                    "input_value",
                    str,
                    description="The input of the map function.",
                )
            ],
            outputs=[
                IOField.build_from("Output", "output", str, description="The output.")
            ],
        )

        def __init__(self, llm_client: LLMClient, **kwargs):
            super().__init__(**kwargs)
            self._llm_client = llm_client

        async def map(self, input_value: str) -> str:
            return f"User: {input_value}\nAI: Hello"

    metadata_name = f"_resource_metadata_{MyLLMClient.__name__}"
    resource_metadata: ResourceMetadata = getattr(MyLLMClient, metadata_name)
    resource_metadata_dict = resource_metadata.to_dict()
    resource_metadata_dict["parameters"][0]["value"] = "dummy_api_key"
    resource_data_id = "uuid_resource_123"
    new_resource_metadata = ResourceMetadata(**resource_metadata_dict)
    resource_data = {resource_data_id: new_resource_metadata}

    metadata = MyLLMOperator.metadata
    dict_data = metadata.to_dict()
    dict_data["parameters"][0]["value"] = resource_data_id
    view_metadata = ViewMetadata(**dict_data)

    new_task = MyLLMOperator.build_from(view_metadata, resource_data)
    assert new_task is not None
    assert await new_task.call("hello") == "User: hello\nAI: Hello"
