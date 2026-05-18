import pytest

from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceLoadResourceParameters


@pytest.mark.parametrize(
    ("data", "expected_space_name"),
    [
        (2, "2"),
        ("2", "2"),
        ({"value": 2}, "2"),
        ({"value": "space_name"}, "space_name"),
        ({"space_name": "space_name"}, "space_name"),
    ],
)
def test_knowledge_resource_parameters_accept_scalar_space_values(
    data, expected_space_name
):
    params = KnowledgeSpaceLoadResourceParameters.from_dict(data)

    assert params.space_name == expected_space_name
    assert params.top_k == 10
