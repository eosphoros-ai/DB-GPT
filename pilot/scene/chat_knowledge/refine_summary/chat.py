from typing import Dict

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.scene.chat_knowledge.refine_summary.prompt import prompt

CFG = Config()


class ExtractRefineSummary(BaseChat):
    chat_scene: str = ChatScene.ExtractRefineSummary.value()

    """get summary by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.ExtractRefineSummary
        super().__init__(
            chat_param=chat_param,
        )

        self.user_input = chat_param["current_user_input"]
        self.existing_answer = chat_param["select_param"]
        # self.extract_mode = chat_param["select_param"]

    def generate_input_values(self):
        input_values = {
            "context": self.user_input,
            "existing_answer": self.existing_answer,
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ExtractRefineSummary.value
