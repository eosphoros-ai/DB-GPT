from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from .out_parser import QueryRewriteParser

CFG = Config()


PROMPT_SCENE_DEFINE = """You are a helpful assistant that generates multiple search queries based on a single input query."""


_DEFAULT_TEMPLATE = """
Generate {nums} search queries related to: {original_query}, queries should be similar and answerable search queries you might have, Provide following comma-separated format: 'queries: <queries>'\n":
 "---------------------\n"
    "Example:"
    "original query: What is RAG."
    "queries:'1. what is rag and how does it work, 2. what are the applications of rag, 3. can you provide examples of rag usage in real-world scenarios'"
    "---------------------\n"
    "original query:: {original_query}\n"
    "queries:\n"
"""

PROMPT_RESPONSE = """"""

PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.QueryRewrite.value(),
    input_variables=["nums", "original_query"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=QueryRewriteParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
from ..v1 import prompt_chatglm
