from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.app.scene.chat_knowledge.extract_entity.out_parser import ExtractEntityParser

CFG = Config()

PROMPT_SCENE_DEFINE = """"""

_DEFAULT_TEMPLATE = """
"A question is provided below. Given the question, extract up to 10 "
    "keywords from the text. Focus on extracting the keywords that we can use "
    "to best lookup answers to the question. Avoid stopwords.\n"
    "Example:"
    "Text: Alice is Bob's mother."
    "KEYWORDS:Alice,mother,Bob\n"
    "---------------------\n"
    "{text}\n"
    "---------------------\n"
    "Provide keywords in the following comma-separated format: 'KEYWORDS: <keywords>'\n"
"""
PROMPT_RESPONSE = """"""


RESPONSE_FORMAT = """"""


PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ExtractEntity.value(),
    input_variables=["text"],
    response_format="",
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractEntityParser(is_stream_out=PROMPT_NEED_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
