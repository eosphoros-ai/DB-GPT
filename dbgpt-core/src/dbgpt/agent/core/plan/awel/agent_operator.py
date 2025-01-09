"""Agent Operator for AWEL."""
import logging
from abc import ABC
from typing import Dict, List, Optional, Type

from dbgpt.core.awel import (
    BranchFunc,
    BranchJoinOperator,
    BranchOperator,
    BranchTaskType,
    MapOperator,
)
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OperatorType,
    Parameter,
    ViewMetadata,
)
from dbgpt.core.awel.trigger.base import Trigger
from dbgpt.core.interface.message import ModelMessageRoleType

# TODO: Don't dependent on MixinLLMOperator
from dbgpt.model.operators.llm_operator import MixinLLMOperator
from dbgpt.util.i18n_utils import _

from .... import ActionOutput
from ....resource.manage import get_resource_manager
from ....util.llm.llm import LLMConfig
from ...agent import Agent, AgentGenerateContext, AgentMessage
from ...agent_manage import get_agent_manager
from ...base_agent import ConversableAgent
from .agent_operator_resource import AWELAgent

logger = logging.getLogger()


class BaseAgentOperator:
    """The abstract operator for an Agent."""

    SHARE_DATA_KEY_MODEL_NAME = "share_data_key_agent_name"

    def __init__(self, agent: Optional[Agent] = None):
        """Create an AgentOperator."""
        self._agent = agent

    @property
    def agent(self) -> Agent:
        """Return the Agent."""
        if not self._agent:
            raise ValueError("agent is not set")
        return self._agent


class WrappedAgentOperator(
    BaseAgentOperator, MapOperator[AgentGenerateContext, AgentGenerateContext], ABC
):
    """The Agent operator.

    Wrap the agent and trigger the agent to generate a reply.
    """

    def __init__(self, agent: Agent, **kwargs):
        """Create an WrappedAgentOperator."""
        super().__init__(agent=agent)
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: AgentGenerateContext) -> AgentGenerateContext:
        """Trigger agent to generate a reply."""
        now_rely_messages: List[AgentMessage] = []
        if not input_value.message:
            raise ValueError("The message is empty.")
        input_message = input_value.message.copy()

        # Isolate the message delivery mechanism and pass it to the operator
        _goal = self.agent.name if self.agent.name else self.agent.role
        current_goal = f"[{_goal}]:"

        if input_message.content:
            current_goal += input_message.content
        input_message.current_goal = current_goal

        # What was received was the User message
        human_message = input_message.copy()
        human_message.role = ModelMessageRoleType.HUMAN
        now_rely_messages.append(human_message)

        # Send a message (no reply required) and pass the message content
        now_message = input_message
        if input_value.rely_messages and len(input_value.rely_messages) > 0:
            now_message = input_value.rely_messages[-1]
        if not input_value.sender:
            raise ValueError("The sender is empty.")
        await input_value.sender.send(
            now_message, self.agent, input_value.reviewer, False
        )

        agent_reply_message = await self.agent.generate_reply(
            received_message=input_message,
            sender=input_value.sender,
            reviewer=input_value.reviewer,
            rely_messages=input_value.rely_messages,
        )
        is_success = agent_reply_message.success

        if not is_success:
            raise ValueError(
                f"The task failed at step {self.agent.role} and the attempt "
                f"to repair it failed. The final reason for "
                f"failure:{agent_reply_message.content}!"
            )

        # What is sent is an AI message
        ai_message = agent_reply_message.copy()
        ai_message.role = ModelMessageRoleType.AI

        now_rely_messages.append(ai_message)

        # Handle user goals and outcome dependencies
        return AgentGenerateContext(
            message=input_message,
            sender=self.agent,
            reviewer=input_value.reviewer,
            # Default single step transfer of information
            rely_messages=now_rely_messages,
            silent=input_value.silent,
            memory=input_value.memory.structure_clone() if input_value.memory else None,
            agent_context=input_value.agent_context,
            llm_client=input_value.llm_client,
            begin_agent=None,
            last_speaker=self.agent,
            already_started=True,
        )


class AWELAgentOperator(
    MixinLLMOperator, MapOperator[AgentGenerateContext, AgentGenerateContext]
):
    """The Agent operator for AWEL."""

    metadata = ViewMetadata(
        label="AWEL Agent Operator",
        name="agent_operator",
        category=OperatorCategory.AGENT,
        description="The Agent operator.",
        parameters=[
            Parameter.build_from(
                "Agent",
                "awel_agent",
                AWELAgent,
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

    def __init__(self, awel_agent: AWELAgent, **kwargs):
        """Create an AgentOperator."""
        MixinLLMOperator.__init__(self)
        MapOperator.__init__(self, **kwargs)
        self.awel_agent = awel_agent

    async def map(
        self,
        input_value: AgentGenerateContext,
    ) -> AgentGenerateContext:
        """Trigger agent to generate a reply."""
        if input_value.already_failed:
            return input_value

        if not input_value.message:
            raise ValueError("The message is empty.")
        input_message = input_value.message.copy()
        input_message.rounds = input_message.rounds + 1
        agent = await self.get_agent(input_value)

        is_retry_chat = False
        # 检测awel flow的启动位置，如果还没启动当前不执行要匹配到启动点才开始执行，如果已经启动则当前需要执行
        if input_value.begin_agent and not input_value.already_started:
            if agent.role != input_value.begin_agent:
                return input_value
            else:
                is_retry_chat = True

        if agent.fixed_subgoal and len(agent.fixed_subgoal) > 0:
            # Isolate the message delivery mechanism and pass it to the operator
            current_goal = f"[{agent.name if agent.name else agent.role}]:"
            if agent.fixed_subgoal:
                current_goal += agent.fixed_subgoal
            input_message.current_goal = current_goal
            input_message.content = agent.fixed_subgoal
        else:
            # Isolate the message delivery mechanism and pass it to the operator
            current_goal = f"[{agent.name if agent.name else agent.role}]:"
            if input_message.content:
                current_goal += input_message.content
            input_message.current_goal = current_goal

        now_rely_messages: List[AgentMessage] = []
        # What was received was the User message
        human_message = input_message.copy()
        human_message.role = ModelMessageRoleType.HUMAN
        now_rely_messages.append(human_message)

        # Send a message (no reply required) and pass the message content

        now_message = input_message
        if input_value.rely_messages and len(input_value.rely_messages) > 0:
            now_message = input_value.rely_messages[-1]
        sender = input_value.sender
        if not sender:
            raise ValueError("The sender is empty.")
        await sender.send(now_message, agent, input_value.reviewer, False)

        agent_reply_message = await agent.generate_reply(
            received_message=input_message,
            sender=input_value.sender,
            reviewer=input_value.reviewer,
            rely_messages=input_value.rely_messages,
            is_retry_chat=is_retry_chat,
            last_speaker_name=input_value.begin_agent,
        )
        if not isinstance(agent_reply_message, AgentMessage):
            raise ValueError(agent_reply_message)

        already_failed = False
        is_success = agent_reply_message.success
        if not is_success:
            already_failed = True

        # What is sent is an AI message
        ai_message: AgentMessage = agent_reply_message.copy()
        ai_message.role = ModelMessageRoleType.AI
        now_rely_messages.append(ai_message)

        # Handle user goals and outcome dependencies
        return AgentGenerateContext(
            message=input_message,
            sender=agent,
            reviewer=input_value.reviewer,
            # Default single step transfer of information
            rely_messages=now_rely_messages,
            silent=input_value.silent,
            memory=input_value.memory.structure_clone() if input_value.memory else None,
            agent_context=input_value.agent_context,
            llm_client=input_value.llm_client,
            begin_agent=None,
            already_failed=already_failed,
            last_speaker=agent,
            already_started=True,
        )

    async def get_agent(
        self,
        input_value: AgentGenerateContext,
    ) -> ConversableAgent:
        """Build the agent."""
        # agent build
        agent_cls: Type[ConversableAgent] = get_agent_manager().get_by_name(
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

        prompt_template = None
        if self.awel_agent.agent_prompt:
            from dbgpt.serve.prompt.api.endpoints import get_service

            prompt_service = get_service()
            prompt_template = prompt_service.get_template(
                self.awel_agent.agent_prompt.code
            )

        resource = get_resource_manager().build_resource(self.awel_agent.resources)
        agent = (
            await agent_cls(**kwargs)
            .bind(input_value.memory)
            .bind(llm_config)
            .bind(input_value.agent_context)
            .bind(resource)
            .bind(prompt_template)
            .build(is_retry_chat=bool(input_value.begin_agent))
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


class AgentBranchOperator(BranchOperator[AgentGenerateContext, AgentGenerateContext]):
    """The intent detection branch operator."""

    metadata = ViewMetadata(
        label=_("Agent Branch Operator"),
        name="agent_branch_operator",
        category=OperatorCategory.AGENT,
        operator_type=OperatorType.BRANCH,
        description=_(
            "Branch the workflow based on the agent actionreport nexspeakers of the request."  # noqa
        ),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Agent Request"),
                "input_value",
                AgentGenerateContext,
                description=_("The input value of the operator."),
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Agent Request"),
                "output_value",
                AgentGenerateContext,
                description=_("The agent request to agent Operator."),
            ),
        ],
    )

    def __init__(self, **kwargs):
        """Create the intent detection branch operator."""
        super().__init__(**kwargs)

    async def branches(
        self,
    ) -> Dict[BranchFunc[AgentGenerateContext], BranchTaskType]:
        """Branch the intent detection result to different tasks."""
        agent_nodes: List[AWELAgentOperator] = [
            node for node in self.downstream if isinstance(node, AWELAgentOperator)
        ]

        download_agent_nodes = set(task for task in agent_nodes)  # noqa
        branch_func_map = {}

        for task_node in download_agent_nodes:
            agent_name = task_node.awel_agent.agent_profile

            def check(r: AgentGenerateContext, outer_task_name=agent_name):
                last_message = r.rely_messages[-1]
                action_output: Optional[ActionOutput] = last_message.action_report

                if not action_output or not action_output.next_speakers:
                    return False

                return outer_task_name in action_output.next_speakers

            branch_func_map[check] = task_node.node_name

        return branch_func_map  # type: ignore


class AgentBranchJoinOperator(BranchJoinOperator[AgentGenerateContext]):
    """The LLM Branch Join Operator.

    Decide which output to keep(streaming or non-streaming).
    """

    metadata = ViewMetadata(
        label=_("Agent Branch Join Operator"),
        name="agent_branch_join_operator",
        category=OperatorCategory.AGENT,
        operator_type=OperatorType.JOIN,
        description=_("Just keep the first non-empty output."),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Agent Output"),
                "agent_output",
                AgentGenerateContext,
                description=_("The Agent output."),
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Branch Output"),
                "agent_output_value",
                AgentGenerateContext,
                description=_("The output value of the operator."),
            ),
        ],
    )

    def __init__(self, **kwargs):
        """Create a new LLM branch join operator."""
        super().__init__(**kwargs)
