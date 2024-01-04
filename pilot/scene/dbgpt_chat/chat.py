import os
from typing import Dict

from pilot.configs.config import Config
from pilot.configs.model_config import EMBEDDING_MODEL_CONFIG
from pilot.scene.base import ChatScene
from pilot.scene.base_chat import BaseChat
from pilot.server.knowledge.api import knowledge_space_service
from pilot.server.knowledge.request.request import KnowledgeSpaceRequest
from .prompt import prompt

CFG = Config()


class ChatWithDbGPT(BaseChat):
    """Chat With DB-GPT"""

    chat_scene: str = ChatScene.DbGPTChat.value()

    def __init__(self, chat_param: Dict):
        """Chat DBA Module Initialization
                Args:
                   - chat_param: Dict
                    - chat_session_id: (str) chat session_id
                    - current_user_input: (str) current user input
                    - model_name:(str) llm model name
                    - select_param:(str) space name
                """
        from pilot.embedding_engine.embedding_engine import EmbeddingEngine
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory

        chat_param["chat_mode"] = ChatScene.DbGPTChat
        super().__init__(chat_param=chat_param)
        self.space_context = self.get_space_context()
        self.top_k = (
            CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            if self.space_context is None
            else int(self.space_context["embedding"]["topk"])
        )
        self.max_token = (
            CFG.KNOWLEDGE_SEARCH_MAX_TOKEN
            if self.space_context is None
            else int(self.space_context["prompt"]["max_token"])
        )

        spaces = knowledge_space_service.get_knowledge_space(
            KnowledgeSpaceRequest(name=CFG.DB_GPT_CHAT_KS, user_id=CFG.DB_GPT_CHAT_ADMIN))
        if len(spaces) != 1:
            raise f"knowledge space {CFG.DB_GPT_CHAT_KS} is not exist or more than one found!"

        vector_store_config = {
            "vector_store_name": CFG.KS_EMBED_PREFIX + str(spaces[0].id),
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
        }
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        self.knowledge_embedding_client = EmbeddingEngine(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config=vector_store_config,
            embedding_factory=embedding_factory,
        )
        self.prompt_template.template_is_strict = False

    async def stream_call(self):
        input_values = self.generate_input_values()
        # Source of knowledge file
        relations = input_values.get("relations")
        last_output = None
        async for output in super().stream_call():
            last_output = output
            yield output

        if (
            CFG.KNOWLEDGE_CHAT_SHOW_RELATIONS
            and last_output
            and type(relations) == list
            and len(relations) > 0
            and hasattr(last_output, "text")
        ):
            last_output.text = (
                last_output.text + "\n\nrelations:\n\n" + ",".join(relations)
            )
            yield last_output

    def generate_input_values(self):
        docs = self.knowledge_embedding_client.similar_search(
            self.current_user_input, self.top_k
        )
        if not docs:
            raise ValueError(
                "you have no knowledge space, please add your knowledge space"
            )
        context = [d.page_content for d in docs]
        context = context[: self.max_token]
        relations = list(
            set([os.path.basename(str(d.metadata.get("source", ""))) for d in docs])
        )
        input_values = {
            "context": context,
            "question": self.current_user_input,
            "relations": relations,
        }
        return input_values

    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")

        # TODO 根据输出信息执行API请求并将结果进行后处理
        return prompt_response

    @property
    def chat_type(self) -> str:
        return ChatScene.DbGPTChat.value

    def get_space_context(self):
        return {"embedding": {"topk": 5}, "prompt": {"max_token": 3500}}
