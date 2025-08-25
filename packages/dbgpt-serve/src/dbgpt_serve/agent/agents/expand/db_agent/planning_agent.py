"""Planner Agent."""

import logging
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import Field
from dbgpt.agent.core.agent import Agent, AgentMessage
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.core.plan.planning_action import ReActAction
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent

logger = logging.getLogger(__name__)


class PlanningAgent(ConversableAgent):
    """Planner Agent.

    Planner agent, realizing task goal planning decomposition through LLM.
    """

    agents: List[ConversableAgent] = Field(default_factory=list)
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "planner",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_name",
        ),
        role=DynConfig(
            "Planning Expert",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_role",
        ),
        goal=DynConfig(
            """一步一步思考为逐步解决问题生成当前可行的路径任务，你需要基于提供给你的背景知识、分析经验再结合历史消息里的分析处理进展和数据状态，对用户输入的异常
            或问题进行专业的分析思考，寻找接下来可行的分析处理方法和路径，并将找到的下一步可行路径整理成一个目标单一明确信息完整的可执行任务，
            每次请只给出一个任务即可, 并将目标分配给合适的代理去完成.如果问题已经可以基于历史信息给出确切结论，
            把结论信息交给{{reporter}}进行整理回复.  同时你思考过程和输出答案请准守下面给出的‘约束’""",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_goal",
        ),
        expand_prompt=DynConfig(
            "### 你可以安排的代理如下:\n {{ agents }}",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_expand_prompt",
        ),
        constraints=DynConfig(
            [
                "每个次给出的任务是为后续的进一步分析补充数据和信息，不要输出不可完成的或依赖路径还没有答案的步骤， 也不要反复生成已经获取过相关信息的任务",
                "请确保生成的任务目标明确信息完整，每个任务只负责解决一件事情，不要把多步多目标需求放到一个任务中,不要过于复杂",
                "请注意分析任务的前后逻辑顺序，如果当前的数据信息还不满足，就不要输出对应任务，直到前置条件满足",
                "生成任务时，确保任务包含所有在用户消息和对话中出现的明确目标参数信息，给出对应参数名称和值，确保不要遗漏任何关键的目标信息",
                "对于任务断言如果没有背景知识支持可以考虑简单确定是否存在数据即可，不要自行构造规则和判断标准",
                "请根据Agent的能力介绍给任务分配的Agent，不要自行理解和随意分配",
            ],
            category="agent",
            key="dbgpt_agent_planning_agent_profile_constraints",
        ),
        desc=DynConfig(
            "你是一个任务规划专家！可以协调智能体，基于提供给你的背景知识、分析经验再结合历史消息里的分析处理进展和数据状态，对用户输入的异常或问题进行专业的分析思考，寻找接下来可行的分析处理方法和路径。",
            category="agent",
            key="dbgpt_agent_planning_agent_profile_desc",
        ),
        examples=DynConfig(
            None,  # noqa: E501
            category="agent",
            key="dbgpt_agent_planning_agent_profile_examples",
        ),
    )
    language: str = "zh"
    report_agent: Optional[ConversableAgent] = None

    def __init__(self, **kwargs):
        """Create a new PlannerAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([ReActAction])

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
        reply_message.context = {
            "agents": "\n".join([f"- {item.name}:{item.desc}" for item in self.agents]),
        }
        return reply_message

    def hire(self, agents: List[ConversableAgent]):
        """Bind the agents to the planner agent."""
        valid_agents = []
        reporter = None
        for agent in agents:
            if isinstance(agent, SummaryAssistantAgent):
                reporter = agent
            else:
                valid_agents.append(agent)
        valid_agents.append(reporter)

        self.report_agent = reporter
        self.agents = valid_agents

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
            "retry_times": self.current_retry_counter,
        }
