from typing import Dict

from dbgpt import SystemApp
from dbgpt.util.tracer import trace
from dbgpt_app.scene import BaseChat, ChatScene


class ChatNormal(BaseChat):
    chat_scene: str = ChatScene.ChatNormal.value()

    keep_end_rounds: int = 10

    """Number of results to return from the query"""

    def __init__(self, chat_param: Dict, system_app: SystemApp = None):
        """ """
        chat_param["chat_mode"] = ChatScene.ChatNormal
        super().__init__(chat_param=chat_param, system_app=system_app)

    @trace()
    async def generate_input_values(self) -> Dict:
        input_values = {"input": self.current_user_input}
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatNormal.value
