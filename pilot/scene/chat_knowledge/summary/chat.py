from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.scene.chat_knowledge.summary.prompt import prompt

CFG = Config()


class ExtractSummary(BaseChat):
    chat_scene: str = ChatScene.ExtractSummary.value()

    """get summary by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.ExtractSummary
        super().__init__(
            chat_param=chat_param,
        )

        self.user_input = chat_param["select_param"]

    async def generate_input_values(self):
        input_values = {
            "context": self.user_input,
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ExtractSummary.value
