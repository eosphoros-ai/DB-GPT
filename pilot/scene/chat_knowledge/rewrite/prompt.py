from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle

from .out_parser import QueryRewriteParser

CFG = Config()


PROMPT_SCENE_DEFINE = """You are a helpful assistant that generates multiple search queries based on a single input query."""

_DEFAULT_TEMPLATE_ZH = """请根据以下主题生成{nums}个相关的搜索查询，这些查询应与原始查询相似并且是人们可能会提出的可回答的搜索问题。请按照以下逗号分隔的格式提供: 'queries：<queries>'：
"---------------------\n"
"示例："
"original_query：什么是RAG。"
"queries：'1. 什么是RAG及其工作原理，2. RAG有哪些应用场景，3. 能否提供RAG在现实世界中的应用实例'"
"---------------------\n"
"original_query：{original_query}\n"
"queries：\n"
"""

_DEFAULT_TEMPLATE_EN = """
Generate {nums} search queries related to: {original_query}, Provide following comma-separated format: 'queries: <queries>'\n":
 "---------------------\n"
    "Example:"
    "original query: What is RAG."
    "queries:'1. what is rag and how does it work, 2. what are the applications of rag, 3. can you provide examples of rag usage in real-world scenarios'"
    "---------------------\n"
    "original query:: {original_query}\n"
    "queries:\n"
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

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
