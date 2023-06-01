import builtins
import importlib

from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_normal.out_parser import NormalChatOutputParser


CFG = Config()

_DEFAULT_TEMPLATE = """ 基于以下已知的信息, 专业、简要的回答用户的问题,
            如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造。 
            已知内容: 
            {context}
            问题:
            {question}
"""



PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatKnowledge.value,
    input_variables=["context", "question"],
    response_format=None,
    template_define=None,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)


CFG.prompt_templates.update({prompt.template_scene: prompt})


