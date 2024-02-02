from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import root_validator
from dbgpt.agent.agents.base_agent_new import ConversableAgent
from dbgpt.agent.agents.llm.llm import LLMConfig, LLMStrategyType
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.core import LLMClient
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OperatorType,
    OptionValue,
    Parameter,
    ResourceCategory,
    ViewMetadata,
    register_resource,
)
from dbgpt.core.interface.operators.prompt_operator import CommonChatPromptTemplate


@register_resource(
    label="Awel Agent Resource",
    name="agent_operator_resource",
    description="The Agent Resource.",
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
            label="Agent Resource Value",
            name="agent_resource_value",
            type=str,
            optional=True,
            default=None,
            description="The agent resource value.",
        ),
    ],
)
class AwelAgentResource(AgentResource):
    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType"""

        name = values.pop("agent_resource_name")
        type = values.pop("agent_resource_type")
        value = values.pop("agent_resource_value")

        values["name"] = name
        values["type"] = ResourceType(type)
        values["name"] = value

        return cls.base_pre_fill(values)


@register_resource(
    label="Awel Agent LLM Config",
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
            resource_category=ResourceCategory.LLM_CLIENT,
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
)
class AwelAgentConfig(LLMConfig):
    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent ResourceType"""
        return cls.base_pre_fill(values)


@register_resource(
    label="Awel Layout Agent",
    name="agent_operator_agent",
    description="The Agent to build the Agent Operator.",
    category=ResourceCategory.AGENT,
    parameters=[
        Parameter.build_from(
            label="Role Name",
            name="name",
            type=str,
            optional=True,
            default=None,
            description="The agent role name.",
        ),
        Parameter.build_from(
            label="Max Retry Time",
            name="max_retry_count",
            type=int,
            optional=True,
            default=None,
            description="The agent max retry time.",
        ),
        Parameter.build_from(
            label="Agent Resource",
            name="agent_resources",
            type=AwelAgentResource,
            resource_category=ResourceCategory.AGENT,
            description="The agent resources.",
        ),
        Parameter.build_from(
            label="Agent Prompt",
            name="agent_prompt",
            type=CommonChatPromptTemplate,
            resource_category=ResourceCategory.AGENT,
            description="The agent prompt.",
        ),
        Parameter.build_from(
            label="Agent LLM Config",
            name="llm_config",
            type=AwelAgentConfig,
            resource_category=ResourceCategory.AGENT,
            description="The agent llm config.",
        ),
    ],
)
class AwelAgent(ConversableAgent):
    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the agent"""

        resources = values.pop("agent_resources")
        agent_prompt = values.pop("agent_prompt")

        values["resources"] = [resources]

        return cls.base_pre_fill(values)
