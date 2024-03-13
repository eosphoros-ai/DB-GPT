from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_normal.out_parser import NormalChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

CFG = Config()

PROMPT_SCENE_DEFINE = """A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. 
    The assistant gives helpful, detailed, professional and polite answers to the user's questions. """


_DEFAULT_TEMPLATE_ZH = """ 基于以下已知的信息, 专业、简要的回答用户的问题,
            如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造。 
            已知内容: 
            {context}
            问题:
            {question}
"""
_DEFAULT_TEMPLATE_EN = """ Based on the known information below, provide users with professional and concise answers to their questions. If the answer cannot be obtained from the provided content, please say: "The information provided in the knowledge base is not sufficient to answer this question." It is forbidden to make up information randomly. 
            known information: 
            {context}
            question:
            {question}
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


PROMPT_NEED_STREAM_OUT = True

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(_DEFAULT_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{question}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatKnowledge.value(),
    stream_out=True,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=False,
)

CFG.prompt_template_registry.register(
    prompt_adapter,
    language=CFG.LANGUAGE,
    is_default=False,
    model_names=["chatglm-6b-int4", "chatglm-6b", "chatglm2-6b", "chatglm2-6b-int4"],
)
