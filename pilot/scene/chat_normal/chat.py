from pilot.scene.base_chat import BaseChat, logger, headers
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config

from pilot.common.markdown_text import (
    generate_markdown_table,
    generate_htm_table,
    datas_to_table_html,
)
from pilot.scene.chat_normal.prompt import prompt

CFG = Config()


class ChatNormal(BaseChat):
    chat_scene: str = ChatScene.ChatNormal.value()

    """Number of results to return from the query"""

    def __init__(self, chat_session_id, user_input):
        """ """
        super().__init__(
            chat_mode=ChatScene.ChatNormal,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )

    def generate_input_values(self):
        input_values = {"input": self.current_user_input}
        return input_values

    def do_action(self, prompt_response):
        return prompt_response

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatNormal.value
