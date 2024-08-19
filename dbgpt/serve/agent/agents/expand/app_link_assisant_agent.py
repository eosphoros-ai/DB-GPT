import logging
from typing import Dict, List, Optional

from dbgpt.agent import Agent, ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.serve.agent.agents.expand.actions.app_link_action import LinkAppAction

logger = logging.getLogger()


class LinkAppAssistantAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "dbgpt",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "App Link",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "根据用户的问题和提供的应用信息，选择一个合适的应用来解决和回答用户的问题,并提取用户输入的关键信息到应用意图的槽位中。",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "请一步一步思考参为用户问题选择一个最匹配的应用来进行用户问题回答，可参考给出示例的应用选择逻辑.",
                "请阅读用户问题，确定问题所属领域和问题意图，按领域和意图匹配应用,如果用户问题意图缺少操作类应用需要的参数，优先使用咨询类型应用，有明确操作目标才使用操作类应用.",
                "仅选择可回答问题的应用即可，不要直接回答用户问题.",
                "如果用户的问题和提供的所有应用全都不相关，则应用code和name都输出为空",
                "注意应用意图定义中如果有槽位信息，再次阅读理解用户输入信息，将对应的内容填入对应槽位参数定义中.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "根据用户问题匹配合适的应用来进行回答.",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_desc",
        ),
    )
    stream_out: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([LinkAppAction])


agent_manage = get_agent_manager()
agent_manage.register_agent(LinkAppAssistantAgent)
