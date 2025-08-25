"""Planner Agent."""

import logging
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import Field
from dbgpt.agent.core.agent import Agent, AgentMessage
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.core.profile import DynConfig, ProfileConfig

from ..actions.planning_action import SrePlanningAction
from .planning_agent import PlanningAgent

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE_ZH = """你是AI数据分析专家，你需要根据将任务进行拆解，先根据KnowledgeAgent查指标知识，再根据数据分析agent获取数据，并且分配给可用Agent。

您要解决的问题是：{{question}}

## 可用Agent列表（请将当前生成的指令任务分配给以下列表中的相应代理以完成列表。）：
{{agents}}

一步一步思考解决问题。在每个步骤中，您的响应应遵循以下 JSON 格式：

{{out_schema}}

开始吧。

"""


# Not needed additional user prompt template
_USER_TEMPLATE = """"""

_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if thought %}Thought: {{ thought }} {% endif %}
{% if action %}Action: {{ action }} {% endif %}
{% if action_input %}Action Input: {{ action_input }} {% endif %}
{% if observation %}Observation: {{ observation }} {% endif %}
"""


class DataPlanningAgent(PlanningAgent):
    """Planner Agent.

    Planner agent, realizing task goal planning decomposition through LLM.
    """

    agents: List[ConversableAgent] = Field(default_factory=list)
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "DataPlanningAgent",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_name",
        ),
        role=DynConfig(
            "DataPlanningAgent",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_role",
        ),
        goal=DynConfig(
            """为了解决每个给定的问题，你需要迭代地指示给出代理进行工作，以对目标系统的遥测文件进行数据分析。通过分析执行结果，你需要逐步逼近答案""",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_goal",
        ),
        system_prompt_template=_SYSTEM_TEMPLATE_ZH,
        # user_prompt_template=_USER_TEMPLATE,
        write_memory_template=_WRITE_MEMORY_TEMPLATE,
        avatar="devid.jpg",
    )
    language: str = "zh"
    current_goal: str = ":探索分析"

    def __init__(self, **kwargs):
        """Create a new PlannerAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([SrePlanningAction])

    async def init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
        sender: Optional[Agent] = None,
    ) -> AgentMessage:
        reply_message = await super().init_reply_message(
            received_message=received_message,
            rely_messages=rely_messages,
            sender=sender,
        )
        # received_message.content = "如何修改列类型"
        reply_message.context = {
            "agents": "\n".join([f"- {item.name}:{item.desc}" for item in self.agents]),
            # "background": schema,
        }
        return reply_message

    def bind_agents(self, agents: List[ConversableAgent]) -> ConversableAgent:
        """Bind the agents to the planner agent."""
        self.agents = agents
        # resources = []
        # for agent in self.agents:
        #     if agent.resource:
        #         resources.append(agent.resource)
        # self.resource = ResourcePack(resources)
        return self

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        reply_message = kwargs.get("reply_message")
        if not reply_message:
            raise "planner agent need reply_message params!"
        return {
            "context": self.not_null_agent_context,
            "plans_memory": self.memory.plans_memory,
            "round": reply_message.rounds,
            "round_id": reply_message.round_id,
        }
