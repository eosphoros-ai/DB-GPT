from typing import Dict

from dbgpt.app.scene import BaseChat, ChatScene


class ExtractTriplet(BaseChat):
    chat_scene: str = ChatScene.ExtractTriplet.value()

    """extracting triplets by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.ExtractTriplet
        super().__init__(
            chat_param=chat_param,
        )

        self.user_input = chat_param["current_user_input"]
        self.extract_mode = chat_param["select_param"]

    async def generate_input_values(self):
        input_values = {
            "text": self.user_input,
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ExtractTriplet.value
