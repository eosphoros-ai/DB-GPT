from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene

from dbgpt.app.scene.chat_knowledge.refine_summary.out_parser import (
    ExtractRefineSummaryParser,
)

CFG = Config()


PROMPT_SCENE_DEFINE = """A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. 
The assistant gives helpful, detailed, professional and polite answers to the user's questions."""

_DEFAULT_TEMPLATE_ZH = (
    """我们已经提供了一个到某一点的现有总结:{existing_answer}\n 请根据你之前推理的内容进行最终的总结,总结回答的时候最好按照1.2.3.进行."""
)

_DEFAULT_TEMPLATE_EN = """
We have provided an existing summary up to a certain point: {existing_answer}\nWe have the opportunity to refine the existing summary (only if needed) with some more context below. 
\nBased on the previous reasoning, please summarize the final conclusion in accordance with points 1.2.and 3.

"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_RESPONSE = """"""


PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ExtractRefineSummary.value(),
    input_variables=["existing_answer"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractRefineSummaryParser(is_stream_out=PROMPT_NEED_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
