from typing import Dict

from dbgpt.app.scene import BaseChat, ChatScene

from dbgpt.app.scene.chat_knowledge.rewrite.prompt import prompt


class QueryRewrite(BaseChat):
    chat_scene: str = ChatScene.QueryRewrite.value()

    """query rewrite by llm"""

    def __init__(self, chat_param: Dict):
        """ """
        chat_param["chat_mode"] = ChatScene.QueryRewrite
        super().__init__(
            chat_param=chat_param,
        )

        self.nums = chat_param["select_param"]
        self.current_user_input = chat_param["current_user_input"]

    async def generate_input_values(self):
        input_values = {
            "nums": self.nums,
            "original_query": self.current_user_input,
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.QueryRewrite.value
