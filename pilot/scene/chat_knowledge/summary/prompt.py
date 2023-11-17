from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_knowledge.summary.out_parser import ExtractSummaryParser

CFG = Config()

# PROMPT_SCENE_DEFINE = """You are an expert Q&A system that is trusted around the world.\nAlways answer the query using the provided context information, and not prior knowledge.\nSome rules to follow:\n1. Never directly reference the given context in your answer.\n2. Avoid statements like 'Based on the context, ...' or 'The context information ...' or anything along those lines."""

PROMPT_SCENE_DEFINE = """"""

_DEFAULT_TEMPLATE_ZH = """请根据提供的上下文信息的进行精简地总结:
{context}
答案尽量精确和简单,不要过长，长度控制在100字左右
"""

_DEFAULT_TEMPLATE_EN = """
Write a quick summary of the following context: 
{context}
the summary should be as concise as possible and not overly lengthy.Please keep the answer within approximately 200 characters.
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_RESPONSE = """"""


RESPONSE_FORMAT = """"""


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ExtractSummary.value(),
    input_variables=["context"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractSummaryParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
