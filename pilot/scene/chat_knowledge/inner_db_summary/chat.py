from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.scene.chat_knowledge.inner_db_summary.prompt import prompt

CFG = Config()


class InnerChatDBSummary(BaseChat):
    chat_scene: str = ChatScene.InnerChatDBSummary.value()

    """Number of results to return from the query"""

    def __init__(
        self,
        chat_session_id,
        user_input,
        db_select,
        db_summary,
    ):
        """ """
        super().__init__(
            chat_mode=ChatScene.InnerChatDBSummary,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )

        self.db_input = db_select
        self.db_summary = db_summary

    def generate_input_values(self):
        input_values = {
            "db_input": self.db_input,
            "db_profile_summary": self.db_summary,
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.InnerChatDBSummary.value
