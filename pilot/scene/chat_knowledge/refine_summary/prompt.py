from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_knowledge.refine_summary.out_parser import ExtractRefineSummaryParser

CFG = Config()


PROMPT_SCENE_DEFINE = """Your job is to produce a final summary."""

_DEFAULT_TEMPLATE = """
We have provided an existing summary up to a certain point: {existing_answer}\nWe have the opportunity to refine the existing summary (only if needed) with some more context below.\n------------\n{context}\n------------\nGiven the new context, refine the original summary.\nIf the context isn't useful, return the original summary.

please use original language.
"""
PROMPT_RESPONSE = """"""


RESPONSE_FORMAT = """"""


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ExtractRefineSummary.value(),
    input_variables=["existing_answer","context"],
    response_format="",
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractRefineSummaryParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
