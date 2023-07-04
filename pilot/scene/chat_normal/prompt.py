import builtins
import importlib

from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_normal.out_parser import NormalChatOutputParser

PROMPT_SCENE_DEFINE = None

CFG = Config()

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatNormal.value(),
    input_variables=["input"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=None,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_templates.update({prompt.template_scene: prompt})
