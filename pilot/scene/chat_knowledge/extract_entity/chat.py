from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.scene.chat_knowledge.extract_entity.prompt import prompt

CFG = Config()


class ExtractEntity(BaseChat):
    chat_scene: str = ChatScene.ExtractEntity.value()

    """extracting entities by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.ExtractEntity
        super().__init__(
            chat_param=chat_param,
        )

        self.user_input = chat_param["current_user_input"]
        self.extract_mode = chat_param["select_param"]

    def generate_input_values(self):
        input_values = {
            "text": self.user_input,
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ExtractEntity.value
