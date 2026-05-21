import pytest

from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceLoadResourceParameters


@pytest.mark.parametrize(
    ("data", "expected_space_name", "expected_name"),
    [
        (2, "2", "knowledge"),
        ("2", "2", "knowledge"),
        ({"value": 2}, "2", "knowledge"),
        ({"value": "space_name"}, "space_name", "knowledge"),
        ({"space_name": "space_name"}, "space_name", "knowledge"),
        (
            {"name": None, "space_name": "space_name"},
            "space_name",
            "knowledge",
        ),
    ],
)
def test_knowledge_resource_parameters_accept_scalar_space_values(
    data, expected_space_name, expected_name
):
    params = KnowledgeSpaceLoadResourceParameters.from_dict(data)

    assert params.name == expected_name
    assert params.space_name == expected_space_name
    assert params.top_k == 10


def test_knowledge_resource_parameters_preserve_explicit_name():
    params = KnowledgeSpaceLoadResourceParameters.from_dict(
        {"name": "custom_resource", "space_name": "space_name"}
    )

    assert params.name == "custom_resource"
    assert params.space_name == "space_name"
