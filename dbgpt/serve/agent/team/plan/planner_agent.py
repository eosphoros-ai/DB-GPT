from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydantic import Field

from dbgpt._private.config import Config
from dbgpt.agent.agents.base_agent_new import ConversableAgent
from dbgpt.agent.resource.resource_api import AgentResource
from .plan_action import PlanAction

CFG = Config()


class PlannerAgent(ConversableAgent):
    """Planner agent, realizing task goal planning decomposition through LLM"""

    agents: List[ConversableAgent] = Field(default_factory=list)

    profile: str = "Planner"
    goal: str = "理解下面每个智能代理和他们的能力，使用给出的资源，通过协调智能代理来解决用户问题。 请发挥你LLM的知识和理解能力，理解用户问题的意图和目标，生成一个可以在没有用户帮助下，由智能代理协作完成目标的任务计划。"
    expand_prompt: str = """可用智能代理:
        {agents}
    """
    constraints: List[str] = [
        "任务计划的每个步骤都应该是为了推进解决用户目标而存在，不要生成无意义的任务步骤，确保每个步骤内目标明确内容完整。",
        "关注任务计划每个步骤的依赖关系和逻辑，被依赖步骤要考虑被依赖的数据，是否能基于当前目标得到，如果不能请在目标中提示要生成被依赖数据。",
        "每个步骤都是一个独立可完成的目标，一定要确保逻辑和信息完整，不要出现类似:'Analyze the retrieved issues data'这样目标不明确，不知道具体要分析啥内容的步骤",
        "请确保只使用上面提到的智能代理，并且可以只使用其中需要的部分，严格根据描述能力和限制分配给合适的步骤，每个智能代理都可以重复使用。",
        "根据用户目标的实际需要使用提供的资源来协助生成计划步骤，不要使用不需要的资源。",
        "每个步骤最好只使用一种资源完成一个子目标，如果当前目标可以分解为同类型的多个子任务，可以生成相互不依赖的并行任务。",
        "数据资源可以被合适的智能代理加载使用，不用考虑数据资源的加载链接问题",
        "尽量合并有顺序依赖的连续相同步骤,如果用户目标无拆分必要，可以生成内容为用户目标的单步任务。",
        "仔细检查计划，确保计划完整的包含了用户问题所涉及的所有信息，并且最终能完成目标，确认每个步骤是否包含了需要用到的资源信息,如URL、资源名等. ",
    ]
    desc: str = "你是一个任务规划专家！可以协调智能代理，分配资源完成复杂的任务目标。"

    examples = """
    user:help me build a sales report summarizing our key metrics and trends
    assisant:[
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
    ]
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([PlanAction])

    def _init_reply_message(self, recive_message):
        reply_message = super()._init_reply_message(recive_message)
        reply_message["context"] = {
            "agents": "\n".join(
                [f"- {item.profile}:{item.desc}" for item in self.agents]
            ),
        }
        return reply_message

    @staticmethod
    def get_unique_resources_codes(resource: AgentResource) -> str:
        return resource.name + "_" + resource.type.value + "_" + resource.value

    def bind_agents(self, agents: List[ConversableAgent]) -> ConversableAgent:
        self.agents = agents
        unique_resources = set()
        for agent in self.agents:
            if agent.resources and len(agent.resources) > 0:
                for resource in agent.resources:
                    if self.get_unique_resources_codes(resource) not in unique_resources:
                        unique_resources.add(self.get_unique_resources_codes(resource))
                        self.resources.append(resource)
        return self

    def prepare_act_param(self) -> Optional[Dict]:
        return {"context": self.agent_context, "plans_memory": self.memory.plans_memory}
