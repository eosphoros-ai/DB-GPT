from typing import List

from pilot.scene.base_chat import BaseChat, logger, headers
from pilot.scene.message import OnceConversation
from pilot.scene.base import ChatScene


class ChatWithPlugin(BaseChat):
    chat_scene: str = ChatScene.ChatExecution.value

    def __init__(self, chat_mode, chat_session_id, current_user_input):
        super().__init__(chat_mode, chat_session_id, current_user_input)

    def call(self):
        super().call()

    def chat_show(self):
        super().chat_show()

    def _load_history(self, session_id: str) -> List[OnceConversation]:
        return super()._load_history(session_id)

    def generate(self, p) -> str:
        return super().generate(p)

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatExecution.value
