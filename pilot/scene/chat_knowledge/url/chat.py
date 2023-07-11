from pilot.embedding_engine.knowledge_type import KnowledgeType
from pilot.scene.base_chat import BaseChat, logger, headers
from pilot.scene.base import ChatScene
from pilot.common.sql_database import Database
from pilot.configs.config import Config

from pilot.common.markdown_text import (
    generate_markdown_table,
    generate_htm_table,
    datas_to_table_html,
)

from pilot.configs.model_config import (
    DATASETS_DIR,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    LLM_MODEL_CONFIG,
    LOGDIR,
)

from pilot.scene.chat_knowledge.url.prompt import prompt
from pilot.embedding_engine.embedding_engine import EmbeddingEngine

CFG = Config()


class ChatUrlKnowledge(BaseChat):
    chat_scene: str = ChatScene.ChatUrlKnowledge.value()

    """Number of results to return from the query"""

    def __init__(self, chat_session_id, user_input, url):
        """ """
        super().__init__(
            chat_mode=ChatScene.ChatUrlKnowledge,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )
        self.url = url
        vector_store_config = {
            "vector_store_name": url.replace(":", ""),
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
        }
        self.knowledge_embedding_client = EmbeddingEngine(
            model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config=vector_store_config,
            knowledge_type=KnowledgeType.URL.value,
            knowledge_source=url,
        )

        # url soruce in vector
        if not self.knowledge_embedding_client.vector_exist():
            self.knowledge_embedding_client.knowledge_embedding()
        logger.info("url embedding success")

    def generate_input_values(self):
        docs = self.knowledge_embedding_client.similar_search(
            self.current_user_input, CFG.KNOWLEDGE_SEARCH_TOP_SIZE
        )
        context = [d.page_content for d in docs]
        context = context[:2000]
        input_values = {"context": context, "question": self.current_user_input}
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatUrlKnowledge.value
