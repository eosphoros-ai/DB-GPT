import logging
from typing import Dict, List, Optional

from dbgpt.agent import Agent, ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.serve.agent.agents.expand.actions.app_link_action import LinkAppAction

logger = logging.getLogger()


class LinkAppAssistantAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "AppLink",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "AppLink",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "根据用户的问题和提供的应用信息，选择一个合适的应用来解决和回答用户的问题。",
            category="agent",
            key="dbgpt_ant_agent_agents_app_link_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "请一步一步思考参为用户问题选择一个最匹配的应用来进行用户问题回答，可参考给出示例的应用选择逻辑.",
                "请阅读用户问题，确定问题所属领域和问题意图，按领域和意图匹配应用,如果用户问题意图缺少操作类应用需要的参数，优先使用咨询类型应用，有明确操作目标才使用操作类应用.",
                "优先按业务范围和领域选择提供的应用来回答用户问题",
                "如果匹配到应用，请只按要求格式输出应用相关信息，不用回答用户问题",
                "如果匹配到应用，请确保将所匹配应用的信息按照如下格式回答:{out_schema}",
                "如果用户的问题和提供的所有应用全都不相关，则请你直接回答用户的问题.不要返回json，也不要返回code为空或者未知的应用",
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
    version: int = 2
    stream_out: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([LinkAppAction])

    def prepare_act_param(
        self,
        recive_message: Optional[Dict],
        sender: Agent,
        rely_messages: Optional[List[Dict]] = None,
    ) -> Optional[Dict]:
        return {"version": self.version}


agent_manage = get_agent_manager()
agent_manage.register_agent(LinkAppAssistantAgent)
