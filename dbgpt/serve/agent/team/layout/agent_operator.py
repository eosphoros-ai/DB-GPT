from abc import ABC
from typing import Dict, List, Optional

from dbgpt.agent.agents.agent_new import Agent, AgentGenerateContext
from dbgpt.agent.agents.agents_manage import agent_manage
from dbgpt.agent.agents.base_agent_new import ConversableAgent
from dbgpt.agent.agents.llm.llm import LLMConfig
from dbgpt.core.awel import BranchFunc, BranchOperator, MapOperator
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OperatorType,
    Parameter,
    ResourceCategory,
    ViewMetadata,
)
from dbgpt.core.awel.trigger.base import Trigger
from dbgpt.core.interface.message import ModelMessageRoleType
from dbgpt.model.operators.llm_operator import MixinLLMOperator

from .agent_operator_resource import AwelAgent


class BaseAgentOperator:
    """The abstract operator for a Agent."""

    SHARE_DATA_KEY_MODEL_NAME = "share_data_key_agent_name"

    def __init__(self, agent: Optional[Agent] = None):
        self._agent: ConversableAgent = agent

    @property
    def agent(self) -> Agent:
        """Return the Agent."""
        if not self._agent:
            raise ValueError("agent is not set")
        return self._agent


class AgentOperator(
    BaseAgentOperator, MapOperator[AgentGenerateContext, AgentGenerateContext], ABC
):
    def __init__(self, agent: Agent, **kwargs):
        super().__init__(agent=agent)
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: AgentGenerateContext) -> AgentGenerateContext:
        now_rely_messages: List[Dict] = []

        # Isolate the message delivery mechanism and pass it to the operator
        input_value.message["current_goal"] = (
            f"[{self._agent.name if self._agent.name else self._agent.profile}]:"
            + input_value.message["content"]
        )
        ###What was received was the User message
        human_message = input_value.message.copy()
        human_message["role"] = ModelMessageRoleType.HUMAN
        now_rely_messages.append(human_message)

        ###Send a message (no reply required) and pass the message content
        now_message = input_value.message
        if input_value.rely_messages and len(input_value.rely_messages) > 0:
            now_message = input_value.rely_messages[-1]
        await input_value.sender.a_send(
            now_message, self._agent, input_value.reviewer, False
        )

        is_success, reply_message = await self._agent.a_generate_reply(
            recive_message=input_value.message,
            sender=input_value.sender,
            reviewer=input_value.reviewer,
            rely_messages=input_value.rely_messages,
        )

        if not is_success:
            raise ValueError(
                f"The task failed at step {self._agent.profile} and the attempt to repair it failed. The final reason for failure:{reply_message['content']}!"
            )

        ###What is sent is an AI message
        ai_message = reply_message
        ai_message["role"] = ModelMessageRoleType.AI
        now_rely_messages.append(ai_message)

        ### Handle user goals and outcome dependencies
        return AgentGenerateContext(
            message=input_value.message,
            sender=self._agent,
            reviewer=input_value.reviewer,
            rely_messages=now_rely_messages,  ## Default single step transfer of information
            silent=input_value.silent,
        )


class AwelAgentOperator(
    MixinLLMOperator, MapOperator[AgentGenerateContext, AgentGenerateContext]
):
    metadata = ViewMetadata(
        label="Agent Operator",
        name="agent_operator",
        category=OperatorCategory.AGENT,
        description="The Agent operator.",
        parameters=[
            Parameter.build_from(
                "Agent",
                "awel_agent",
                AwelAgent,
                description="The dbgpt agent.",
            ),
        ],
        inputs=[
            IOField.build_from(
                "Agent Operator Request",
                "agent_operator_request",
                AgentGenerateContext,
                "The Agent Operator request.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Agent Operator Output",
                "agent_operator_output",
                AgentGenerateContext,
                description="The Agent Operator output.",
            )
        ],
    )

    def __init__(self, awel_agent: AwelAgent, **kwargs):
        MixinLLMOperator.__init__(self)
        MapOperator.__init__(self, **kwargs)
        self.awel_agent = awel_agent

    async def map(
        self,
        input_value: AgentGenerateContext,
    ) -> AgentGenerateContext:
        now_message = input_value.message
        agent = await self.get_agent(input_value)
        if agent.fixed_subgoal and len(agent.fixed_subgoal) > 0:
            # Isolate the message delivery mechanism and pass it to the operator
            input_value.message["current_goal"] = (
                f"[{agent.name if agent.name else agent.profile}]:"
                + agent.fixed_subgoal
            )
            now_message["content"] = agent.fixed_subgoal
        else:
            # Isolate the message delivery mechanism and pass it to the operator
            input_value.message["current_goal"] = (
                f"[{agent.name if agent.name else agent.profile}]:"
                + input_value.message["content"]
            )

        now_rely_messages: List[Dict] = []
        ###What was received was the User message
        human_message = input_value.message.copy()
        human_message["role"] = ModelMessageRoleType.HUMAN
        now_rely_messages.append(human_message)

        ###Send a message (no reply required) and pass the message content

        if input_value.rely_messages and len(input_value.rely_messages) > 0:
            now_message = input_value.rely_messages[-1]
        await input_value.sender.a_send(now_message, agent, input_value.reviewer, False)

        is_success, reply_message = await agent.a_generate_reply(
            recive_message=input_value.message,
            sender=input_value.sender,
            reviewer=input_value.reviewer,
            rely_messages=input_value.rely_messages,
        )

        if not is_success:
            raise ValueError(
                f"The task failed at step {agent.profile} and the attempt to repair it failed. The final reason for failure:{reply_message['content']}!"
            )

        ###What is sent is an AI message
        ai_message = reply_message
        ai_message["role"] = ModelMessageRoleType.AI
        now_rely_messages.append(ai_message)

        ### Handle user goals and outcome dependencies
        return AgentGenerateContext(
            message=input_value.message,
            sender=agent,
            reviewer=input_value.reviewer,
            rely_messages=now_rely_messages,  ## Default single step transfer of information
            silent=input_value.silent,
            memory=input_value.memory,
            agent_context=input_value.agent_context,
            resource_loader=input_value.resource_loader,
            llm_client=input_value.llm_client,
            round_index=agent.consecutive_auto_reply_counter,
        )

    async def get_agent(
        self,
        input_value: AgentGenerateContext,
    ):
        ### agent build
        agent_cls: ConversableAgent = agent_manage.get_by_name(
            self.awel_agent.agent_profile
        )
        llm_config = self.awel_agent.llm_config

        if not llm_config:
            if input_value.llm_client:
                llm_config = LLMConfig(llm_client=input_value.llm_client)
            else:
                llm_config = LLMConfig(llm_client=self.llm_client)
        else:
            if not llm_config.llm_client:
                if input_value.llm_client:
                    llm_config.llm_client = input_value.llm_client
                else:
                    llm_config.llm_client = self.llm_client

        kwargs = {}
        if self.awel_agent.role_name:
            kwargs["name"] = self.awel_agent.role_name
        if self.awel_agent.fixed_subgoal:
            kwargs["fixed_subgoal"] = self.awel_agent.fixed_subgoal

        agent = (
            await agent_cls(**kwargs)
            .bind(input_value.memory)
            .bind(llm_config)
            .bind(input_value.agent_context)
            .bind(self.awel_agent.resources)
            .bind(input_value.resource_loader)
            .build()
        )

        return agent


class AgentDummyTrigger(Trigger):
    """Http trigger for AWEL.

    Http trigger is used to trigger a DAG by http request.
    """

    metadata = ViewMetadata(
        label="Agent Trigger",
        name="agent_trigger",
        category=OperatorCategory.AGENT,
        operator_type=OperatorType.INPUT,
        description="Trigger your workflow by agent",
        inputs=[],
        parameters=[],
        outputs=[
            IOField.build_from(
                "Agent Operator Context",
                "agent_operator_context",
                AgentGenerateContext,
                description="The Agent Operator output.",
            )
        ],
    )

    def __init__(
        self,
        **kwargs,
    ) -> None:
        """Initialize a HttpTrigger."""
        super().__init__(**kwargs)

    async def trigger(self, **kwargs) -> None:
        """Trigger the DAG. Not used in HttpTrigger."""
        raise NotImplementedError("Dummy trigger does not support trigger.")
