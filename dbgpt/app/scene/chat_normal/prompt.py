from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_normal.out_parser import NormalChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

PROMPT_SCENE_DEFINE_EN = "You are a helpful AI assistant."
PROMPT_SCENE_DEFINE_ZH = "你是一个有用的 AI 助手。"

CFG = Config()

PROMPT_SCENE_DEFINE = (
    PROMPT_SCENE_DEFINE_ZH if CFG.LANGUAGE == "zh" else PROMPT_SCENE_DEFINE_EN
)

PROMPT_NEED_STREAM_OUT = True

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(PROMPT_SCENE_DEFINE),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatNormal.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=True,
)

CFG.prompt_template_registry.register(
    prompt_adapter, language=CFG.LANGUAGE, is_default=True
)
