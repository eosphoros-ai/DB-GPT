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
    "Strictly define the output based on the given intent. Do not generate the intent and "
    "slot attributes by yourself. If the intent does not define a slot, the output should "
    "not include the slot.",
    "Select the appropriate intent to answer the user's question based on user input. "
    "If no intent can be matched, the output of app_code' will be empty.",
    "If there is no 'Slots' definition in the selected intent definition, make sure the "
    "output slot content is empty and do not create any slot information yourself.",
    "If there is a 'Slots' definition in the selected intent definition, extract the value "
    "of the specific slot attribute from the user input. If the value of the slot attribute "
    "cannot be obtained, ensure that the slot attribute value output is empty.",
    "When extracting the slot value, please be careful to only obtain the valid value part. "
    "Do not fill in auxiliary descriptions, attributes, prompts or description information, "
    "and do not appear content like 'not provided by the user'.",
    "When the complete slot attribute value defined by the intent cannot be collected, a "
    "prompt will be proactively sent to the user to remind the user to supplement the missing "
    "slot data.",
]
CONSTRAINTS_ZH = [
    "严格根给出的意图定义输出，不要自行生成意图和槽位属性，意图没有定义槽位则输出也不应该包含槽位.",
    "根据用户输入选择合适的意图回答用户问题，如无法匹配到任何意图，app_code'输出为空.",
    "如果选择的意图定义中没有'Slots'定义,则确保输出槽位内容为空，不要自行创造任何槽位信息",
    "如果选择的意图定义中有'Slots'定义,从用户输入中提取具体槽位属性的值,如果无法获取到槽位属性的值，则确保槽位属性值输出空.",
    "槽位值提取时请注意只获取有效值部分,不要填入辅助描述、定语、提示或者描述信息，不要出现类似'用户未提供'这样的内容.",
    "无法收集到完整的意图定义的槽位属性值时，主动像用户发起提示，提醒用户补充缺槽位数据.",
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
