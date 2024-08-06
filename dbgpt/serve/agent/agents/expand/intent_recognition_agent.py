import logging

from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.serve.agent.agents.expand.actions.intent_recognition_action import (
    IntentRecognitionAction,
)

logger = logging.getLogger()


class IntentRecognitionAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Kevin",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_name",
        ),
        role=DynConfig(
            "IntentRecognitionExpert",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_role",
        ),
        goal=DynConfig(
            "从下面的意图定义中选择一个和用户问题最匹配的意图，并根据要求和输出格式返回意图完整信息。",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_goal",
        ),
        retry_goal=DynConfig(
            "阅读下面用户提供的最近消息内容，并把当前用户输入信息补充到最近消息中的意图信息里并返回补充后的意图信息。",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_retry_goal",
        ),
        constraints=DynConfig(
            [
                "严格根给出的意图定义输出，不要自行生成意图和槽位属性，意图没有定义槽位则输出也不应该包含槽位.",
                "从用户输入和历史对话信息中提取意图定义中槽位属性的值，如果无法获取到槽位属性对应的目标信息，则槽位值输出空.",
                "槽位值提取时请注意只获取有效值部分，不要填入辅助描述或定语",
                "确保意图定义的槽位属性不管是否获取到值，都要输出全部定义给出的槽位属性，没有找到值的输出槽位名和空值.",
                "请确保如果用户问题中未提供意图槽位定义的内容，则槽位值必须为空，不要在槽位里填‘用户未提供’这类无效信息.",
                "如果用户问题内容提取的信息和匹配到的意图槽位无法完全对应，则生成新的问题向用户提问，提示用户补充缺少的槽位数据.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_retry_constraints",
        ),
        retry_constraints=DynConfig(
            [
                "阅读用户提供最近消息对话信息，把当前用户输入中信息提取补充到历史对话意图中并按原意图格式输出，不要丢失属性.",
                "如果用户没有明确要求修改，不要修改最近消息中意图中已经存在的意图和槽位值，仅补充新的内容进去.",
                "槽位值提取时请注意只获取有效值部分，不要填入辅助描述或定语",
                "从用户输入和最近消息息中提取意图定义中槽位的值，如果无法获取到槽位对应的目标信息，则槽位值输出空.",
                "确保意图定义的槽位不管是否获取到值，都要输出全部槽位属性，没有找到值的输出槽位名和空值.",
                "如果槽位值依然无法完全对应填满，则继续生成新的问题向用户提问，提示用户补充缺少的槽位数据.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_constraints",
        ),
        desc=DynConfig(
            "识别用户意图.",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_desc",
        ),
    )

    stream_out: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([IntentRecognitionAction])

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        if is_retry_chat:
            return ("", None)
        else:
            return await super().load_resource(question, is_retry_chat)


agent_manage = get_agent_manager()
agent_manage.register_agent(IntentRecognitionAgent)
