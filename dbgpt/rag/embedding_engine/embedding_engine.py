from typing import Optional

from langchain.text_splitter import TextSplitter

from dbgpt.rag.embedding_engine.embedding_factory import (
    EmbeddingFactory,
    DefaultEmbeddingFactory,
)
from dbgpt.rag.embedding_engine.knowledge_type import (
    get_knowledge_embedding,
    KnowledgeType,
)
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class EmbeddingEngine:
    """EmbeddingEngine provide a chain process include(read->text_split->data_process->index_store) for knowledge document embedding into vector store.
    1.knowledge_embedding:knowledge document source into vector store.(Chroma, Milvus, Weaviate)
    2.similar_search: similarity search from vector_store
    how to use reference:https://db-gpt.readthedocs.io/en/latest/modules/knowledge.html
    how to integrate:https://db-gpt.readthedocs.io/en/latest/modules/knowledge/pdf/pdf_embedding.html
    Example:
    .. code-block:: python
        embedding_model = "your_embedding_model"
        vector_store_type = "Chroma"
        chroma_persist_path = "your_persist_path"
        vector_store_config = {
            "vector_store_name": "document_test",
            "vector_store_type": vector_store_type,
            "chroma_persist_path": chroma_persist_path,
        }

        # it can be .md,.pdf,.docx, .csv, .html
        document_path = "your_path/test.md"
        embedding_engine = EmbeddingEngine(
            knowledge_source=document_path,
            knowledge_type=KnowledgeType.DOCUMENT.value,
            model_name=embedding_model,
            vector_store_config=vector_store_config,
        )
        # embedding document content to vector store
        embedding_engine.knowledge_embedding()
    """

    def __init__(
        self,
        model_name,
        vector_store_config,
        knowledge_type: Optional[str] = KnowledgeType.DOCUMENT.value,
        knowledge_source: Optional[str] = None,
        source_reader: Optional = None,
        text_splitter: Optional[TextSplitter] = None,
        embedding_factory: EmbeddingFactory = None,
    ):
        """Initialize with knowledge embedding client, model_name, vector_store_config, knowledge_type, knowledge_source
        Args:
           - model_name: model_name
           - vector_store_config: vector store config: Dict
           - knowledge_type: Optional[KnowledgeType]
           - knowledge_source: Optional[str]
           - source_reader: Optional[BaseLoader]
           - text_splitter: Optional[TextSplitter]
           - embedding_factory: EmbeddingFactory
        """
        self.knowledge_source = knowledge_source
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.knowledge_type = knowledge_type
        if not embedding_factory:
            embedding_factory = DefaultEmbeddingFactory()
        self.embeddings = embedding_factory.create(model_name=self.model_name)
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
        """vector db similar search in vector database.
         Return topk docs.
        Args:
           - text: query text
           - topk: top k
        """
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        # https://github.com/chroma-core/chroma/issues/657
        ans = vector_client.similar_search(text, topk)
        return ans

    def similar_search_with_scores(self, text, topk, score_threshold: float = 0.3):
        """
        similar_search_with_score in vector database.
        Return docs and relevance scores in the range [0, 1].
        Args:
            doc(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs,0 is dissimilar, 1 is most similar.
        """
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        ans = vector_client.similar_search_with_scores(text, topk, score_threshold)
        return ans

    def vector_exist(self):
        """vector db is exist"""
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        return vector_client.vector_name_exists()

    def delete_by_ids(self, ids):
        """delete vector db by ids
        Args:
           - ids: vector ids
        """
        vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        vector_client.delete_by_ids(ids=ids)
