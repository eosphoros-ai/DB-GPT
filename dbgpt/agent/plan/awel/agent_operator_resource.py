"""The AWEL Agent Operator Resource."""
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field, root_validator
from dbgpt.core import LLMClient
from dbgpt.core.awel.flow import (
    FunctionDynamicOptions,
    OptionValue,
    Parameter,
    ResourceCategory,
    register_resource,
)

from ...core.agent_manage import get_agent_manager
from ...core.llm.llm import LLMConfig, LLMStrategyType
from ...resource.resource_api import AgentResource, ResourceType


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
            options=[
                OptionValue(label=item.name, name=item.value, value=item.value)
                for item in ResourceType
            ],
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
    alias=["dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgentResource"],
)
class AWELAgentResource(AgentResource):
    """AWEL Agent Resource."""

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
        name = values.pop("agent_resource_name")
        type = values.pop("agent_resource_type")
        value = values.pop("agent_resource_value")

        values["name"] = name
        values["type"] = ResourceType(type)
        values["value"] = value

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
    alias=["dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgentConfig"],
)
class AWELAgentConfig(LLMConfig):
    """AWEL Agent Config."""

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
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
            type=AWELAgentResource,
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
    ],
    alias=["dbgpt.serve.agent.team.layout.agent_operator_resource.AwelAgent"],
)
class AWELAgent(BaseModel):
    """AWEL Agent."""

    agent_profile: str
    role_name: Optional[str] = None
    llm_config: Optional[LLMConfig] = None
    resources: List[AgentResource] = Field(default_factory=list)
    fixed_subgoal: Optional[str] = None

    class Config:
        """Config for the BaseModel."""

        arbitrary_types_allowed = True

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType."""
        resource = values.pop("agent_resource")
        llm_config = values.pop("agent_llm_Config")

        if resource is not None:
            values["resources"] = [resource]

        if llm_config is not None:
            values["llm_config"] = llm_config

        return values
