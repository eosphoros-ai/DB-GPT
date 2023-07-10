from typing import Optional

from chromadb.errors import NotEnoughElementsException
from langchain.embeddings import HuggingFaceEmbeddings

from pilot.configs.config import Config
from pilot.embedding_engine.knowledge_type import get_knowledge_embedding, KnowledgeType
from pilot.vector_store.connector import VectorStoreConnector

CFG = Config()


class EmbeddingEngine:
    def __init__(
        self,
        model_name,
        vector_store_config,
        knowledge_type: Optional[str] = KnowledgeType.DOCUMENT.value,
        knowledge_source: Optional[str] = None,
    ):
        """Initialize with knowledge embedding client, model_name, vector_store_config, knowledge_type, knowledge_source"""
        self.knowledge_source = knowledge_source
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.knowledge_type = knowledge_type
        self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        self.vector_store_config["embeddings"] = self.embeddings

    def knowledge_embedding(self):
        self.knowledge_embedding_client = self.init_knowledge_embedding()
        self.knowledge_embedding_client.source_embedding()

    def knowledge_embedding_batch(self, docs):
        # docs = self.knowledge_embedding_client.read_batch()
        return self.knowledge_embedding_client.index_to_store(docs)

    def read(self):
        self.knowledge_embedding_client = self.init_knowledge_embedding()
        return self.knowledge_embedding_client.read_batch()

    def init_knowledge_embedding(self):
        return get_knowledge_embedding(
            self.knowledge_type, self.knowledge_source, self.vector_store_config
        )

    def similar_search(self, text, topk):
        vector_client = VectorStoreConnector(
            CFG.VECTOR_STORE_TYPE, self.vector_store_config
        )
        try:
            ans = vector_client.similar_search(text, topk)
        except NotEnoughElementsException:
            ans = vector_client.similar_search(text, 1)
        return ans

    def vector_exist(self):
        vector_client = VectorStoreConnector(
            CFG.VECTOR_STORE_TYPE, self.vector_store_config
        )
        return vector_client.vector_name_exists()

    def delete_by_ids(self, ids):
        vector_client = VectorStoreConnector(
            CFG.VECTOR_STORE_TYPE, self.vector_store_config
        )
        vector_client.delete_by_ids(ids=ids)
