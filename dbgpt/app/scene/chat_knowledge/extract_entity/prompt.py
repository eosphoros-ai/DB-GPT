from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_knowledge.extract_entity.out_parser import ExtractEntityParser
from dbgpt.core import ChatPromptTemplate, HumanPromptTemplate

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

PROMPT_NEED_NEED_STREAM_OUT = False

prompt = ChatPromptTemplate(
    messages=[
        # SystemPromptTemplate.from_template(PROMPT_SCENE_DEFINE),
        HumanPromptTemplate.from_template(_DEFAULT_TEMPLATE + PROMPT_RESPONSE),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ExtractEntity.value(),
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ExtractEntityParser(is_stream_out=PROMPT_NEED_NEED_STREAM_OUT),
    need_historical_messages=False,
)

CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
