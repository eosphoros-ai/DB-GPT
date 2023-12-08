from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene

from dbgpt.app.scene.chat_normal.out_parser import NormalChatOutputParser

PROMPT_SCENE_DEFINE = None

CFG = Config()


PROMPT_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatNormal.value(),
    input_variables=["input"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=None,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
)

# CFG.prompt_templates.update({prompt.template_scene: prompt})
CFG.prompt_template_registry.register(prompt, language=CFG.LANGUAGE, is_default=True)
