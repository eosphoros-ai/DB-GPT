from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene


from dbgpt.app.scene.chat_knowledge.extract_triplet.out_parser import (
    ExtractTripleParser,
)


CFG = Config()

PROMPT_SCENE_DEFINE = """"""

_DEFAULT_TEMPLATE = """
"Some text is provided below. Given the text, extract up to 10"
    "knowledge triplets in the form of (subject, predicate, object). Avoid stopwords.\n"
    "---------------------\n"
    "Example:"
    "Text: Alice is Bob's mother."
    "Triplets:\n(Alice, is mother of, Bob)\n"
    "Text: Philz is a coffee shop founded in Berkeley in 1982.\n"
    "Triplets:\n"
    "(Philz, is, coffee shop)\n"
    "(Philz, founded in, Berkeley)\n"
    "(Philz, founded in, 1982)\n"
    "---------------------\n"
    "Text: {text}\n"
    "Triplets:\n"
   ensure Respond in the following List(Tuple) format:
    '(Stephen Curry, plays for, Golden State Warriors)\n(Stephen Curry, known for, shooting skills)\n(Stephen Curry, attended, Davidson College)\n(Stephen Curry, led, team to success)'
"""
PROMPT_RESPONSE = """"""


RESPONSE_FORMAT = """"""


PROMPT_NEED_NEED_STREAM_OUT = False

prompt = PromptTemplate(
    template_scene=ChatScene.ExtractTriplet.value(),
    input_variables=["text"],
    response_format="",
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE + PROMPT_RESPONSE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractTripleParser(is_stream_out=PROMPT_NEED_NEED_STREAM_OUT),
)

CFG.prompt_template_registry.register(prompt, is_default=True)
