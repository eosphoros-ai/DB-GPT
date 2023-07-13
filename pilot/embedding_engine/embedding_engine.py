from typing import Optional

from chromadb.errors import NotEnoughElementsException
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import TextSplitter

from pilot.embedding_engine.knowledge_type import get_knowledge_embedding, KnowledgeType
from pilot.vector_store.connector import VectorStoreConnector


class EmbeddingEngine:
    """EmbeddingEngine provide a chain process include(read->text_split->data_process->index_store) for knowledge document embedding into vector store.
    1.knowledge_embedding:knowledge document source into vector store.(Chroma, Milvus, Weaviate)
    2.similar_search: similarity search from vector_store
    how to use reference:https://db-gpt.readthedocs.io/en/latest/modules/knowledge.html
    how to integrate:https://db-gpt.readthedocs.io/en/latest/modules/knowledge/pdf/pdf_embedding.html
    """

    def __init__(
        self,
        model_name,
        vector_store_config,
        knowledge_type: Optional[str] = KnowledgeType.DOCUMENT.value,
        knowledge_source: Optional[str] = None,
        source_reader: Optional = None,
        text_splitter: Optional[TextSplitter] = None,
    ):
        """Initialize with knowledge embedding client, model_name, vector_store_config, knowledge_type, knowledge_source"""
        self.knowledge_source = knowledge_source
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.knowledge_type = knowledge_type
        self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        self.vector_store_config["embeddings"] = self.embeddings
        self.source_reader = source_reader
        self.text_splitter = text_splitter

    def knowledge_embedding(self):
        """source embedding is chain process.read->text_split->data_process->index_store"""
        self.knowledge_embedding_client = self.init_knowledge_embedding()
        self.knowledge_embedding_client.source_embedding()

    def knowledge_embedding_batch(self, docs):
        """Deprecation"""
        # docs = self.knowledge_embedding_client.read_batch()
        return self.knowledge_embedding_client.index_to_store(docs)

    def read(self):
        """Deprecation"""
        self.knowledge_embedding_client = self.init_knowledge_embedding()
        return self.knowledge_embedding_client.read_batch()

    def init_knowledge_embedding(self):
        return get_knowledge_embedding(
            self.knowledge_type,
            self.knowledge_source,
            self.vector_store_config,
            self.source_reader,
            self.text_splitter,
        )

    def similar_search(self, text, topk):
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        try:
            ans = vector_client.similar_search(text, topk)
        except NotEnoughElementsException:
            ans = vector_client.similar_search(text, 1)
        return ans

    def vector_exist(self):
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        return vector_client.vector_name_exists()

    def delete_by_ids(self, ids):
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        vector_client.delete_by_ids(ids=ids)
