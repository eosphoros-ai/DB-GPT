"""Planner Agent."""

from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import Field

from ...resource.pack import ResourcePack
from ..agent import Agent, AgentMessage
from ..base_agent import ConversableAgent
from ..plan.plan_action import PlanAction
from ..profile import DynConfig, ProfileConfig


class PlannerAgent(ConversableAgent):
    """Planner Agent.

    Planner agent, realizing task goal planning decomposition through LLM.
    """

    agents: List[ConversableAgent] = Field(default_factory=list)

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Planner",
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_name",
        ),
        role=DynConfig(
            "Planner",
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_role",
        ),
        goal=DynConfig(
            "Understand each of the following intelligent agents and their "
            "capabilities, using the provided resources, solve user problems by "
            "coordinating intelligent agents. Please utilize your LLM's knowledge "
            "and understanding ability to comprehend the intent and goals of the "
            "user's problem, generating a task plan that can be completed through"
            " the collaboration of intelligent agents without user assistance.",
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_goal",
        ),
        expand_prompt=DynConfig(
            "Available Intelligent Agents:\n {{ agents }}",
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_expand_prompt",
        ),
        constraints=DynConfig(
            [
                "Every step of the task plan should exist to advance towards solving "
                "the user's goals. Do not generate meaningless task steps; ensure "
                "that each step has a clear goal and its content is complete.",
                "Pay attention to the dependencies and logic of each step in the task "
                "plan. For the steps that are depended upon, consider the data they "
                "depend on and whether it can be obtained based on the current goal. "
                "If it cannot be obtained, please indicate in the goal that the "
                "dependent data needs to be generated.",
                "Each step must be an independently achievable goal. Ensure that the "
                "logic and information are complete. Avoid steps with unclear "
                "objectives, like 'Analyze the retrieved issues data,' where it's "
                "unclear what specific content needs to be analyzed.",
                "Please ensure that only the intelligent agents mentioned above are "
                "used, and you may use only the necessary parts of them. Allocate "
                "them to appropriate steps strictly based on their described "
                "capabilities and limitations. Each intelligent agent can be reused.",
                "Utilize the provided resources to assist in generating the plan "
                "steps according to the actual needs of the user's goals. Do not use "
                "unnecessary resources.",
                "Each step should ideally use only one type of resource to accomplish "
                "a sub-goal. If the current goal can be broken down into multiple "
                "subtasks of the same type, you can create mutually independent "
                "parallel tasks.",
                "Data resources can be loaded and utilized by the appropriate "
                "intelligent agents without the need to consider the issues related "
                "to data loading links.",
                "Try to merge continuous steps that have sequential dependencies. If "
                "the user's goal does not require splitting, you can create a "
                "single-step task with content that is the user's goal.",
                "Carefully review the plan to ensure it comprehensively covers all "
                "information involved in the user's problem and can ultimately "
                "achieve the goal. Confirm whether each step includes the necessary "
                "resource information, such as URLs, resource names, etc.",
            ],
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_constraints",
        ),
        desc=DynConfig(
            "You are a task planning expert! You can coordinate intelligent agents"
            " and allocate resources to achieve complex task goals.",
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_desc",
        ),
        examples=DynConfig(
            """
user:help me build a sales report summarizing our key metrics and trends
assistants:[
    {{
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve total sales, average sales, and number of transactions grouped by "product_category"'.",
        "rely": ""
    }},
    {{
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Retrieve monthly sales and transaction number trends.",
        "rely": ""
    }},
    {{
        "serial_number": "3",
        "agent": "Reporter",
        "content": "Integrate analytical data into the format required to build sales reports.",
        "rely": "1,2"
    }}
]""",  # noqa: E501
            category="agent",
            key="dbgpt_agent_plan_planner_agent_profile_examples",
        ),
    )
    _goal_zh: str = (
        "理解下面每个智能体(agent)和他们的能力，使用给出的资源，通过协调智能体来解决"
        "用户问题。 请发挥你LLM的知识和理解能力，理解用户问题的意图和目标，生成一个可以"
        "在没有用户帮助下，由智能体协作完成目标的任务计划。"
    )
    _expand_prompt_zh: str = "可用智能体(agent):\n {{ agents }}"

    _constraints_zh: List[str] = [
        "任务计划的每个步骤都应该是为了推进解决用户目标而存在，不要生成无意义的任务步骤，确保每个步骤内目标明确内容完整。",
        "关注任务计划每个步骤的依赖关系和逻辑，被依赖步骤要考虑被依赖的数据，是否能基于当前目标得到，如果不能请在目标中提示要生成被依赖数据。",
        "每个步骤都是一个独立可完成的目标，一定要确保逻辑和信息完整，不要出现类似:"
        "'Analyze the retrieved issues data'这样目标不明确，不知具体要分析啥内容的步骤",
        "请确保只使用上面提到的智能体，并且可以只使用其中需要的部分，严格根据描述能力和限制分配给合适的步骤，每个智能体都可以重复使用。",
        "根据用户目标的实际需要使用提供的资源来协助生成计划步骤，不要使用不需要的资源。",
        "每个步骤最好只使用一种资源完成一个子目标，如果当前目标可以分解为同类型的多个子任务，可以生成相互不依赖的并行任务。",
        "数据资源可以被合适的智能体加载使用，不用考虑数据资源的加载链接问题",
        "尽量合并有顺序依赖的连续相同步骤,如果用户目标无拆分必要，可以生成内容为用户目标的单步任务。",
        "仔细检查计划，确保计划完整的包含了用户问题所涉及的所有信息，并且最终能完成目标"
        "，确认每个步骤是否包含了需要用到的资源信息,如URL、资源名等. ",
    ]
    _desc_zh: str = "你是一个任务规划专家！可以协调智能体，分配资源完成复杂的任务目标。"

    def __init__(self, **kwargs):
        """Create a new PlannerAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([PlanAction])

    def _init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        reply_message.context = {
            "agents": "\n".join([f"- {item.role}:{item.desc}" for item in self.agents]),
        }
        return reply_message

    def bind_agents(self, agents: List[ConversableAgent]) -> ConversableAgent:
        """Bind the agents to the planner agent."""
        self.agents = agents
        resources = []
        for agent in self.agents:
            if agent.resource:
                resources.append(agent.resource)
        self.resource = ResourcePack(resources)
        return self

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        return {
            "context": self.not_null_agent_context,
            "plans_memory": self.memory.plans_memory,
        }
