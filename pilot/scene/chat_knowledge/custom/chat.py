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

from pilot.scene.chat_knowledge.custom.prompt import prompt
from pilot.embedding_engine.embedding_engine import EmbeddingEngine

CFG = Config()


class ChatNewKnowledge(BaseChat):
    chat_scene: str = ChatScene.ChatNewKnowledge.value()

    """Number of results to return from the query"""

    def __init__(self, chat_session_id, user_input, knowledge_name):
        """ """
        super().__init__(
            chat_mode=ChatScene.ChatNewKnowledge,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )
        self.knowledge_name = knowledge_name
        vector_store_config = {
            "vector_store_name": knowledge_name,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
        }
        self.knowledge_embedding_client = EmbeddingEngine(
            model_name=LLM_MODEL_CONFIG["text2vec"],
            vector_store_config=vector_store_config,
        )

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
        return ChatScene.ChatNewKnowledge.value
