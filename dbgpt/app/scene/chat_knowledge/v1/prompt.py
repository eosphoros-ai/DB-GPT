from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene

from dbgpt.app.scene.chat_normal.out_parser import NormalChatOutputParser

CFG = Config()

PROMPT_SCENE_DEFINE = """A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. 
The assistant gives helpful, detailed, professional and polite answers to the user's questions. """


_DEFAULT_TEMPLATE_ZH = """ 基于以下已知的信息, 专业、简要的回答用户的问题,
            如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造, 回答的时候最好按照1.2.3.点进行总结。 
            已知内容: 
            {context}
            问题:
            {question},请使用和用户相同的语言进行回答.
"""
_DEFAULT_TEMPLATE_EN = """ Based on the known information below, provide users with professional and concise answers to their questions. If the answer cannot be obtained from the provided content, please say: "The information provided in the knowledge base is not sufficient to answer this question." It is forbidden to make up information randomly. When answering, it is best to summarize according to points 1.2.3.
            known information: 
            {context}
            question:
            {question},when answering, use the same language as the "user".
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


PROMPT_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatKnowledge.value(),
    input_variables=["context", "question"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, language=CFG.LANGUAGE, is_default=True)
