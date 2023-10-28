import os
from typing import Dict

from pilot.component import ComponentType
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.configs.model_config import (
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    EMBEDDING_MODEL_CONFIG,
)

from pilot.scene.chat_knowledge.v1.prompt import prompt
from pilot.server.knowledge.service import KnowledgeService
from pilot.utils.executor_utils import blocking_func_to_async

CFG = Config()


class ChatKnowledge(BaseChat):
    chat_scene: str = ChatScene.ChatKnowledge.value()

    """KBQA Chat Module"""

    def __init__(self, chat_param: Dict):
        """Chat Knowledge Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) space name
        """
        from pilot.embedding_engine.embedding_engine import EmbeddingEngine
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory

        self.knowledge_space = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatKnowledge
        super().__init__(
            chat_param=chat_param,
        )
        self.space_context = self.get_space_context(self.knowledge_space)
        self.top_k = (
            CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            if self.space_context is None
            else int(self.space_context["embedding"]["topk"])
        )
        # self.recall_score = CFG.KNOWLEDGE_SEARCH_TOP_SIZE if self.space_context is None else self.space_context["embedding"]["recall_score"]
        self.max_token = (
            CFG.KNOWLEDGE_SEARCH_MAX_TOKEN
            if self.space_context is None
            else int(self.space_context["prompt"]["max_token"])
        )
        vector_store_config = {
            "vector_store_name": self.knowledge_space,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
        }
        from pilot.graph_engine.graph_factory import RAGGraphFactory

        self.rag_engine = CFG.SYSTEM_APP.get_component(
            ComponentType.RAG_GRAPH_DEFAULT.value, RAGGraphFactory
        ).create()
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
        input_values = await self.generate_input_values()
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

    async def generate_input_values(self) -> Dict:
        if self.space_context:
            self.prompt_template.template_define = self.space_context["prompt"]["scene"]
            self.prompt_template.template = self.space_context["prompt"]["template"]
        # docs = self.knowledge_embedding_client.similar_search(
        #     self.current_user_input, self.top_k
        # )
        docs = await blocking_func_to_async(
            self._executor,
            self.knowledge_embedding_client.similar_search,
            self.current_user_input,
            self.top_k,
        )
        docs = await self.rag_engine.search(query=self.current_user_input)
        # docs = self.knowledge_embedding_client.similar_search(
        #     self.current_user_input, self.top_k
        # )
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

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatKnowledge.value()

    def get_space_context(self, space_name):
        service = KnowledgeService()
        return service.get_space_context(space_name)
