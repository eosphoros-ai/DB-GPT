from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from .out_parser import QueryRewriteParser

CFG = Config()


PROMPT_SCENE_DEFINE = """You are a helpful assistant that generates multiple search queries based on a single input query."""

_DEFAULT_TEMPLATE_ZH = """请根据原问题优化生成{nums}个相关的搜索查询，这些查询应与原始查询相似并且是人们可能会提出的可回答的搜索问题。请勿使用任何示例中提到的内容，确保所有生成的查询均独立于示例，仅基于提供的原始查询。请按照以下逗号分隔的格式提供: 'queries：<queries>'：
"original_query：{original_query}\n"
"queries：\n"
"""

_DEFAULT_TEMPLATE_EN = """
Generate {nums} search queries related to: {original_query}, Provide following comma-separated format: 'queries: <queries>'\n":
    "original query:: {original_query}\n"
    "queries:\n"
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_RESPONSE = """"""


PROMPT_NEED_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.QueryRewrite.value(),
    input_variables=["nums", "original_query"],
    response_format=None,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=QueryRewriteParser(is_stream_out=PROMPT_NEED_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
