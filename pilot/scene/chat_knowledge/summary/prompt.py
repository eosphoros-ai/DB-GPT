from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from pilot.scene.chat_knowledge.summary.out_parser import ExtractSummaryParser

CFG = Config()

# PROMPT_SCENE_DEFINE = """You are an expert Q&A system that is trusted around the world.\nAlways answer the query using the provided context information, and not prior knowledge.\nSome rules to follow:\n1. Never directly reference the given context in your answer.\n2. Avoid statements like 'Based on the context, ...' or 'The context information ...' or anything along those lines."""

PROMPT_SCENE_DEFINE = """Your job is to produce a final summary."""

# _DEFAULT_TEMPLATE = """
# Context information from multiple sources is below.\n---------------------\n
# {context}
# Given the information from multiple sources and not prior knowledge, answer the query.\nQuery: Describe what the provided text is about. Also describe some of the questions that this text can answer. \nAnswer: "
# """

_DEFAULT_TEMPLATE = """
Write a concise summary of the following context: 
{context}
please use original language.
"""
PROMPT_RESPONSE = """"""


RESPONSE_FORMAT = """"""


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ExtractSummary.value(),
    input_variables=["context"],
    response_format="",
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractSummaryParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
