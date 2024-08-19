import logging

from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.serve.agent.agents.expand.actions.intent_recognition_action import (
    IntentRecognitionAction,
)

logger = logging.getLogger()

GOAL_EN = (
    "Understand the user input information, select an intention that best matches the "
    "user input from the intention definition of the known information, and output the "
    "intention information as required."
)
GOAL_ZH = "理解用户输入信息，从已知信息的意图定义中选择一个和用户输入最匹配的意图，并按要求输出意图信息."

RETRY_GOAL_EN = (
    "Read the content of the recent messages provided by the following users, "
    "extract and supplement the current user input information into the intent "
    "information in the recent messages, and return the supplemented intent information."
)

RETRY_GOAL_ZH = "阅读下面用户提供的最近消息内容，并把当前用户输入信息提取补充到最近消息中的意图信息里，并返回补充后的意图信息。"

CONSTRAINTS_EN = [
    "According to the user input information, select and match from the given intent definition. "
    "If no intent is matched, 'intent' and 'app_code' will be output as empty. Do not generate "
    "intent and slot attributes by yourself.",
    "The selected intent does not have a slots attribute defined, so make sure the output json "
    "does not include the 'slots' attribute.",
    "Extract the value of the slot attribute in the intent definition from user input and historical "
    "dialogue information. If the target information corresponding to the slot attribute cannot be "
    "obtained, the slot value output is empty.",
    "When extracting slot values, please be careful to only obtain the valid value part and do not "
    "fill in auxiliary descriptions or attributes.",
    "Make sure that the slot attributes defined by intention will output all the slot attributes "
    "given by the definition regardless of whether the value is obtained. If the value is not found, "
    "the slot name and null value will be output.",
    "Please ensure that if the content of the intent slot definition is not provided in the user "
    "question, the slot value must be empty, and do not fill in invalid information such as 'user "
    "not provided' in the slot value.",
    "If the information extracted from the user's question content does not completely correspond to "
    "the matched intention slot, a new question will be generated to ask the user and prompt the user "
    "to supplement the missing slot data.",
]
CONSTRAINTS_ZH = [
    "根据用户输入信息，从给出的意图定义中进行选择匹配，无法匹配到任何意图'intent'和'app_code'都输出为空，不要输出任何未定义的意图.",
    "请确保按意图定义输出槽位属性，不要自行创造任何槽位属性，如果意图定义没有槽位属性，则确保槽位输出位空"
    "从用户输入和历史对话信息中提取意图定义中槽位属性的值，如果无法获取到槽位属性的值，则确保槽位值输出空，不要在槽位值里输出提示或者描述信息，不要出现类似'用户未提供'这样的内容.",
    "槽位值提取时请注意只获取有效值部分，不要填入辅助描述或定语",
    "如果无法收集到完整的意图定义的槽位属性的值，主动像用户发起提示，提醒用户补充缺槽位数据.",
]

RETRY_CONSTRAINTS_EN = [
    "Read the recent message dialogue information provided by the user, extract and supplement the "
    "information input by the current user into the historical dialogue intent, and output it in the "
    "original intent format without losing attributes.",
    "If the user does not explicitly request modification, do not modify the existing intent and "
    "slot value in the intent in the recent message, only add new content.",
    "When extracting slot values, please be careful to only obtain the valid value part "
    "and do not fill in auxiliary descriptions or attributes.",
    "Extract the value of the slot in the intent definition from user input and recent messages. "
    "If the target information corresponding to the slot cannot be obtained, the slot value output is empty.",
    "Make sure that all slot attributes of the slot defined by the intention are output regardless of "
    "whether the value is obtained, and the slot name and null value are output if the value is not found.",
    "If the slot value still cannot be completely filled, new questions will continue to be generated "
    "to ask the user, prompting the user to supplement the missing slot data.",
]
RETRY_CONSTRAINTS_ZH = [
    "阅读用户提供最近消息对话信息，把当前用户输入中信息提取补充到历史对话意图中并按原意图格式输出，不要丢失属性.",
    "如果用户没有明确要求修改，不要修改最近消息中意图中已经存在的意图和槽位值，仅补充新的内容进去.",
    "槽位值提取时请注意只获取有效值部分，不要填入辅助描述或定语",
    "从用户输入和最近消息息中提取意图定义中槽位的值，如果无法获取到槽位对应的目标信息，则槽位值输出空.",
    "确保意图定义的槽位不管是否获取到值，都要输出全部槽位属性，没有找到值的输出槽位名和空值.",
    "如果槽位值依然无法完全对应填满，则继续生成新的问题向用户提问，提示用户补充缺少的槽位数据.",
]


class IntentRecognitionAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Kevin",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_name",
        ),
        role=DynConfig(
            "Intent Recognition Expert",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_role",
        ),
        goal=DynConfig(
            GOAL_EN,
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_goal",
        ),
        retry_goal=DynConfig(
            RETRY_GOAL_EN,
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_retry_goal",
        ),
        constraints=DynConfig(
            CONSTRAINTS_EN,
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_retry_constraints",
        ),
        retry_constraints=DynConfig(
            RETRY_CONSTRAINTS_EN,
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Identify user intent.",
            category="agent",
            key="dbgpt_ant_agent_agents_intent_recognition_agent_profile_desc",
        ),
    )

    stream_out: bool = False
    language: str = "zh"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([IntentRecognitionAction])
        if self.language == "zh":
            self.profile.goal.default = GOAL_ZH
            self.profile.retry_goal.default = RETRY_GOAL_ZH
            self.profile.constraints.default = CONSTRAINTS_ZH
            self.profile.retry_constraints.default = RETRY_CONSTRAINTS_ZH

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        if is_retry_chat:
            return ("", None)
        else:
            return await super().load_resource(question, is_retry_chat)


agent_manage = get_agent_manager()
agent_manage.register_agent(IntentRecognitionAgent)
