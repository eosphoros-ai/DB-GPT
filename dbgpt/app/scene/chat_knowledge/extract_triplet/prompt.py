from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_knowledge.extract_triplet.out_parser import (
    ExtractTripleParser,
)
from dbgpt.core import ChatPromptTemplate, HumanPromptTemplate

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


PROMPT_NEED_NEED_STREAM_OUT = False


prompt = ChatPromptTemplate(
    messages=[
        # SystemPromptTemplate.from_template(PROMPT_SCENE_DEFINE),
        HumanPromptTemplate.from_template(_DEFAULT_TEMPLATE + PROMPT_RESPONSE),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ExtractTriplet.value(),
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractTripleParser(is_stream_out=PROMPT_NEED_NEED_STREAM_OUT),
    need_historical_messages=False,
)

CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
