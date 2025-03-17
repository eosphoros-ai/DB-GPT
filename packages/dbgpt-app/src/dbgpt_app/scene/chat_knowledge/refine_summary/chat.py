from typing import Type

from dbgpt import SystemApp
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.base_chat import ChatParam
from dbgpt_serve.core.config import GPTsAppCommonConfig


class ExtractRefineSummary(BaseChat):
    """extract final summary by llm"""

    chat_scene: str = ChatScene.ExtractRefineSummary.value()

    @classmethod
    def param_class(cls) -> Type[GPTsAppCommonConfig]:
        return GPTsAppCommonConfig

    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """ """
        super().__init__(
            chat_param=chat_param,
            system_app=system_app,
        )

        self.existing_answer = chat_param.select_param

    async def generate_input_values(self):
        input_values = {
            # "context": self.user_input,
            "existing_answer": self.existing_answer,
        }
        return input_values

    def stream_plugin_call(self, text):
        """return summary label"""
        return f"<summary>{text}</summary>"
