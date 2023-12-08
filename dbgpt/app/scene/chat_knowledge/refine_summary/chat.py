from typing import Dict

from dbgpt.app.scene import BaseChat, ChatScene


class ExtractRefineSummary(BaseChat):
    chat_scene: str = ChatScene.ExtractRefineSummary.value()

    """extract final summary by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.ExtractRefineSummary
        super().__init__(
            chat_param=chat_param,
        )

        self.existing_answer = chat_param["select_param"]

    async def generate_input_values(self):
        input_values = {
            # "context": self.user_input,
            "existing_answer": self.existing_answer,
        }
        return input_values

    def stream_plugin_call(self, text):
        """return summary label"""
        return f"<summary>{text}</summary>"

    @property
    def chat_type(self) -> str:
        return ChatScene.ExtractRefineSummary.value
