import json

from dbgpt.agent.core.plan.awel.agent_operator_resource import (
    AWELAgentKnowledgeResource,
)


def test_knowledge_resource_serializes_parameters():
    resource = AWELAgentKnowledgeResource(
        agent_resource_name="kb",
        agent_resource_value="2",
        agent_resource_recall_topk=5,
    )

    assert json.loads(resource.value) == {
        "name": "kb",
        "space_name": "2",
        "top_k": 5,
    }


def test_knowledge_resource_serializes_default_top_k():
    resource = AWELAgentKnowledgeResource(
        agent_resource_name="kb",
        agent_resource_value="2",
    )

    assert json.loads(resource.value)["top_k"] == 3


def test_knowledge_resource_serializes_missing_name():
    resource = AWELAgentKnowledgeResource(agent_resource_value="2")

    assert json.loads(resource.value) == {"space_name": "2", "top_k": 3}
