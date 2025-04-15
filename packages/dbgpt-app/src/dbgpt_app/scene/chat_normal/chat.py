from typing import Type

from dbgpt import SystemApp
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.base_chat import ChatParam
from dbgpt_app.scene.chat_normal.config import ChatNormalConfig


class ChatNormal(BaseChat):
    chat_scene: str = ChatScene.ChatNormal.value()

    @classmethod
    def param_class(cls) -> Type[ChatNormalConfig]:
        return ChatNormalConfig

    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """ """
        super().__init__(chat_param=chat_param, system_app=system_app)
