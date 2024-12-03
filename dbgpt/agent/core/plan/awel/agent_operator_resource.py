"""Agent operator define."""

import json
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_validator
from dbgpt.core import LLMClient
from dbgpt.core.awel.flow import (
    FunctionDynamicOptions,
    OptionValue,
    Parameter,
    ResourceCategory,
    register_resource,
)

from ....resource.base import AgentResource, ResourceType
from ....resource.manage import get_resource_manager
from ....util.llm.llm import LLMConfig, LLMStrategyType
from ...agent_manage import get_agent_manager


def _agent_resource_prompt_values() -> List[OptionValue]:
    from dbgpt.serve.prompt.api.endpoints import get_service

    prompt_service = get_service()
    prompts = prompt_service.get_target_prompt()
    return [
        OptionValue(label=pmt.prompt_name, name=pmt.prompt_code, value=pmt.prompt_code)
        for pmt in prompts
        if pmt.prompt_code
    ]


def _load_resource_types():
    resources = get_resource_manager().get_supported_resources()
    return [OptionValue(label=item, name=item, value=item) for item in resources.keys()]


@register_resource(
    label="AWEL Agent Resource",
    name="agent_operator_resource",
    description="The Agent Resource.",
    category=ResourceCategory.AGENT,
    parameters=[
        Parameter.build_from(
            label="Agent Resource Type",
            name="agent_resource_type",
            type=str,
            optional=True,
            default=None,
            options=FunctionDynamicOptions(func=_load_resource_types),
        ),
        Parameter.build_from(
            label="Agent Resource Name",
            name="agent_resource_name",
            type=str,
            optional=True,
            default=None,
            description="The agent resource name.",
        ),
        Parameter.build_from(
            label="Agent Resource Value",
            name="agent_resource_value",
            type=str,
            optional=True,
            default=None,
            description="The agent resource value.",
        ),
    ],
    alias=[
        "dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgentResource",
        "dbgpt.agent.core.plan.awel.agent_operator_resource.AWELAgentResource",
    ],
)
class AWELAgentResource(AgentResource):
    """AWEL Agent Resource."""

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
        if not isinstance(values, dict):
            return values
        name = values.pop("agent_resource_name")
        type = values.pop("agent_resource_type")
        value = values.pop("agent_resource_value")

        values["name"] = name
        values["type"] = ResourceType(type)
        values["value"] = value

        return values


def _agent_resource_knowledge_values(
    user_id: Optional[str] = None,
) -> List[OptionValue]:
    from dbgpt.app.knowledge.api import knowledge_space_service
    from dbgpt.app.knowledge.request.request import KnowledgeSpaceRequest

    knowledge_spaces = knowledge_space_service.get_knowledge_space(
        KnowledgeSpaceRequest(user_id=user_id)
    )
    return [
        OptionValue(label=ks.name, name=str(ks.id), value=str(ks.id))
        for ks in knowledge_spaces
    ]


@register_resource(
    label="Awel Agent Resource Knowledge",
    name="agent_resource_knowledge",
    description="The Agent Resource Knowledge.",
    category=ResourceCategory.AGENT,
    parameters=[
        Parameter.build_from(
            label="Agent Resource Name",
            name="agent_resource_name",
            type=str,
            optional=True,
            default=None,
            description="The agent resource name.",
        ),
        Parameter.build_from(
            label="Agent Resource Value",
            name="agent_resource_value",
            type=str,
            optional=True,
            default=None,
            description="The agent resource value.",
            options=FunctionDynamicOptions(func=_agent_resource_knowledge_values),
        ),
        Parameter.build_from(
            label="Agent Knowledge Resource Recall TopK",
            name="agent_resource_recall_topk",
            type=str,
            default=3,
            optional=True,
            description="The agent resource recall topk.",
        ),
    ],
    alias=[
        "dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgentKnowledgeResource",  # noqa
        "dbgpt.agent.core.plan.awel.agent_operator_resource.AWELAgentKnowledgeResource",
    ],
)
class AWELAgentKnowledgeResource(AgentResource):
    """AWELAgentKnowledgeResource."""

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
        value = values.pop("agent_resource_value")
        name = values.pop("agent_resource_name")
        top_k = (
            values.pop("agent_resource_recall_topk")
            if "agent_resource_recall_topk" in values
            else None
        )

        values["type"] = ResourceType.Knowledge
        values["value"] = value
        values["name"] = name
        if top_k:
            values["context"] = {"top_k": int(top_k)}
        return values


@register_resource(
    label="Awel Agent Prompt",
    name="agent_prompt",
    description="The Agent Prompt.",
    category=ResourceCategory.AGENT,
    parameters=[
        Parameter.build_from(
            label="Agent Prompt Code",
            name="agent_prompt_code",
            type=str,
            optional=True,
            default=None,
            description="The agent prompt code.",
            options=FunctionDynamicOptions(func=_agent_resource_prompt_values),
        ),
    ],
    alias=[
        "dbgpt.serve.agent.team.layout.agent_operator_resource.AgentPrompt",
        "dbgpt.agent.core.plan.awel.agent_operator_resource.AgentPrompt",
    ],
)
class AgentPrompt(BaseModel):
    """Agent Prompt resource."""

    code: str

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
        code = values.pop("agent_prompt_code")
        values["code"] = code

        return values


@register_resource(
    label="AWEL Agent LLM Config",
    name="agent_operator_llm_config",
    description="The Agent LLM Config.",
    category=ResourceCategory.AGENT,
    parameters=[
        Parameter.build_from(
            "LLM Client",
            "llm_client",
            LLMClient,
            optional=True,
            default=None,
            description="The LLM Client.",
        ),
        Parameter.build_from(
            label="Agent LLM Strategy",
            name="llm_strategy",
            type=str,
            optional=True,
            default=None,
            options=[
                OptionValue(label=item.name, name=item.value, value=item.value)
                for item in LLMStrategyType
            ],
            description="The Agent LLM Strategy.",
        ),
        Parameter.build_from(
            label="Agent LLM Strategy Value",
            name="strategy_context",
            type=str,
            optional=True,
            default=None,
            description="The agent LLM Strategy Value.",
        ),
    ],
    alias=[
        "dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgentConfig",
        "dbgpt.agent.core.plan.awel.agent_operator_resource.AWELAgentConfig",
    ],
)
class AWELAgentConfig(LLMConfig):
    """AWEL Agent Config."""

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Prefill the agent ResourceType."""
        strategy_context = values.pop("strategy_context")

        if strategy_context is not None:
            values["strategy_context"] = json.dumps(strategy_context.split(","))

        return values


def _agent_resource_option_values() -> List[OptionValue]:
    return [
        OptionValue(label=item["name"], name=item["name"], value=item["name"])
        for item in get_agent_manager().list_agents()
    ]


@register_resource(
    label="AWEL Layout Agent",
    name="agent_operator_agent",
    description="The Agent to build the Agent Operator.",
    category=ResourceCategory.AGENT,
    parameters=[
        Parameter.build_from(
            label="Agent Profile",
            name="agent_profile",
            type=str,
            description="Which agent want use.",
            options=FunctionDynamicOptions(func=_agent_resource_option_values),
        ),
        Parameter.build_from(
            label="Role Name",
            name="role_name",
            type=str,
            optional=True,
            default=None,
            description="The agent role name.",
        ),
        Parameter.build_from(
            label="Fixed Gogal",
            name="fixed_subgoal",
            type=str,
            optional=True,
            default=None,
            description="The agent fixed gogal.",
        ),
        Parameter.build_from(
            label="Agent Resource",
            name="agent_resource",
            type=AgentResource,
            optional=True,
            default=None,
            description="The agent resource.",
        ),
        Parameter.build_from(
            label="Agent LLM  Config",
            name="agent_llm_Config",
            type=AWELAgentConfig,
            optional=True,
            default=None,
            description="The agent llm config.",
        ),
        Parameter.build_from(
            label="Agent Prompt",
            name="agent_prompt",
            type=AgentPrompt,
            optional=True,
            default=None,
            description="The agent prompt.",
        ),
    ],
    alias=[
        "dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgent",
        "dbgpt.agent.core.plan.awel.agent_operator_resource.AWELAgent",
    ],
)
class AWELAgent(BaseModel):
    """AWEL Agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_profile: str
    role_name: Optional[str] = None
    llm_config: Optional[LLMConfig] = None
    agent_prompt: Optional[AgentPrompt] = None
    resources: List[AgentResource] = Field(default_factory=list)
    fixed_subgoal: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
        if not isinstance(values, dict):
            return values
        resource = values.pop("agent_resource")
        llm_config = values.pop("agent_llm_Config")
        if "agent_prompt" in values:
            agent_prompt = values.pop("agent_prompt")
        else:
            agent_prompt = None

        if resource is not None:
            values["resources"] = [resource]

        if llm_config is not None:
            values["llm_config"] = llm_config

        if agent_prompt is not None:
            values["agent_prompt"] = agent_prompt
        return values
