import dataclasses

import pytest

from dbgpt.agent.resource.base import AgentResource, Resource, ResourceType
from dbgpt.agent.resource.manage import ResourceManager
from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceLoadResourceParameters


@dataclasses.dataclass
class _DynamicKnowledgeSpaceLoadResourceParameters(
    KnowledgeSpaceLoadResourceParameters
):
    """Mirror the dynamic parameter class built by the knowledge resource."""

    space_name: str = dataclasses.field(
        default=None, metadata={"valid_values": [{"label": "kb", "key": "2"}]}
    )


def test_from_dict_accepts_int_space_id():
    params = KnowledgeSpaceLoadResourceParameters.from_dict(2)

    assert params.space_name == "2"
    assert params.name == "2"


def test_from_dict_accepts_str_space_id():
    params = KnowledgeSpaceLoadResourceParameters.from_dict("2")

    assert params.space_name == "2"
    assert params.name == "2"


def test_from_dict_reads_legacy_value_field():
    params = KnowledgeSpaceLoadResourceParameters.from_dict({"value": "2"})

    assert params.space_name == "2"
    assert params.name == "2"


def test_from_dict_defaults_missing_name_to_space_name():
    params = KnowledgeSpaceLoadResourceParameters.from_dict({"space_name": "kb-1"})

    assert params.space_name == "kb-1"
    assert params.name == "kb-1"


def test_from_dict_keeps_explicit_name_and_top_k():
    params = KnowledgeSpaceLoadResourceParameters.from_dict(
        {"name": "my-kb", "space_name": "2", "top_k": 4}
    )

    assert params.name == "my-kb"
    assert params.space_name == "2"
    assert params.top_k == 4


def test_dynamic_subclass_from_dict_accepts_int_space_id():
    params = _DynamicKnowledgeSpaceLoadResourceParameters.from_dict(2)

    assert params.space_name == "2"
    assert params.name == "2"


def test_from_dict_requires_space():
    with pytest.raises(ValueError, match="space_name"):
        KnowledgeSpaceLoadResourceParameters.from_dict({})


class _FakeKnowledgeResource(Resource):
    """A resource class that builds the dynamic knowledge parameter class."""

    @classmethod
    def type(cls) -> ResourceType:
        return ResourceType.Knowledge

    @property
    def name(self) -> str:
        return "fake-knowledge"

    @classmethod
    def resource_parameters_class(cls, **kwargs):
        return _DynamicKnowledgeSpaceLoadResourceParameters


def test_build_resource_by_type_accepts_scalar_value():
    manager = ResourceManager(None)
    manager.register_resource(_FakeKnowledgeResource)
    resource = AgentResource(type=ResourceType.Knowledge.value, value="2")

    params = manager.build_resource_by_type(
        ResourceType.Knowledge.value, resource, return_resource=False
    )

    assert params["space_name"] == "2"
    assert params["name"] == "2"


def test_build_resource_by_type_defaults_missing_name():
    manager = ResourceManager(None)
    manager.register_resource(_FakeKnowledgeResource)
    resource = AgentResource(
        type=ResourceType.Knowledge.value,
        value='{"space_name": "2", "top_k": 5}',
    )

    params = manager.build_resource_by_type(
        ResourceType.Knowledge.value, resource, return_resource=False
    )

    assert params["name"] == "2"
    assert params["space_name"] == "2"
    assert params["top_k"] == 5
