import builtins
import importlib

from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_normal.out_parser import NormalChatOutputParser


CFG = Config()

_DEFAULT_TEMPLATE = """ Based on the known information, provide professional and concise answers to the user's questions. If the answer cannot be obtained from the provided content, please say: 'The information provided in the knowledge base is not sufficient to answer this question.' Fabrication is prohibited.。 
            known information: 
            {context}
            question:
            {question}
"""


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatUrlKnowledge.value,
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
