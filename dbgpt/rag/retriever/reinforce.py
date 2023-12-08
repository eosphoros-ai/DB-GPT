from typing import List

from dbgpt.app.scene import ChatScene
from dbgpt.app.scene import BaseChat


class QueryReinforce:
    """
    query reinforce, include query rewrite, query correct
    """

    def __init__(
        self, query: str = None, model_name: str = None, llm_chat: BaseChat = None
    ):
        """query reinforce
        Args:
            - query: str, user query
            - model_name: str, llm model name
        """
        self.query = query
        self.model_name = model_name
        self.llm_chat = llm_chat

    async def rewrite(self) -> List[str]:
        """query rewrite"""
        from dbgpt._private.chat_util import llm_chat_response_nostream
        import uuid

        chat_param = {
            "chat_session_id": uuid.uuid1(),
            "current_user_input": self.query,
            "select_param": 2,
            "model_name": self.model_name,
            "model_cache_enable": False,
        }
        tasks = [
            llm_chat_response_nostream(
                ChatScene.QueryRewrite.value(), **{"chat_param": chat_param}
            )
        ]
        from dbgpt._private.chat_util import run_async_tasks

        queries = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        queries = list(
            filter(
                lambda content: "LLMServer Generate Error" not in content,
                queries,
            )
        )
        return queries[0]

    def correct(self) -> List[str]:
        pass
