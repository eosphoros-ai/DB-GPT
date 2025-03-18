from typing import Dict, Type

from dbgpt import SystemApp
from dbgpt.util.tracer import trace
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

    @trace()
    async def generate_input_values(self) -> Dict:
        input_values = {"input": self.current_user_input}
        return input_values
