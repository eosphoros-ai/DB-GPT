import os
from typing import Any, List, Optional

from dbgpt.rag.chunk import Chunk
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.retriever.embedding import EmbeddingRetriever
from dbgpt.serve.rag.assembler.base import BaseAssembler
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class EmbeddingAssembler(BaseAssembler):
    """Embedding Assembler

    Example:

    .. code-block:: python

        from dbgpt.rag.assembler import EmbeddingAssembler

        pdf_path = "path/to/document.pdf"
        knowledge = KnowledgeFactory.from_file_path(pdf_path)
        assembler = EmbeddingAssembler.load_from_knowledge(
            knowledge=knowledge,
            embedding_model="text2vec",
        )
    """

    def __init__(
        self,
        knowledge: Knowledge,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embedding_factory: Optional[EmbeddingFactory] = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.
        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embedding_factory: (Optional[EmbeddingFactory]) EmbeddingFactory to use.
            vector_store_connector: (Optional[VectorStoreConnector]) VectorStoreConnector to use.
        """
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")
        self._vector_store_connector = vector_store_connector
        from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory

        self._embedding_model = embedding_model
        if self._embedding_model:
            embedding_factory = embedding_factory or DefaultEmbeddingFactory(
                default_model_name=self._embedding_model
            )
            self.embedding_fn = embedding_factory.create(self._embedding_model)
        if self._vector_store_connector.vector_store_config.embedding_fn is None:
            self._vector_store_connector.vector_store_config.embedding_fn = (
                self.embedding_fn
            )

        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: Knowledge,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embedding_factory: Optional[EmbeddingFactory] = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
    ) -> "EmbeddingAssembler":
        """Load document embedding into vector store from path.
        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embedding_factory: (Optional[EmbeddingFactory]) EmbeddingFactory to use.
            vector_store_connector: (Optional[VectorStoreConnector]) VectorStoreConnector to use.
        Returns:
             EmbeddingAssembler
        """
        from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory

        embedding_factory = embedding_factory or DefaultEmbeddingFactory(
            default_model_name=embedding_model or os.getenv("EMBEDDING_MODEL_PATH")
        )
        return cls(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            embedding_model=embedding_model,
            embedding_factory=embedding_factory,
            vector_store_connector=vector_store_connector,
        )

    def persist(self) -> List[str]:
        """Persist chunks into vector store.

        Returns:
            List[str]: List of chunk ids.
        """
        return self._vector_store_connector.load_document(self._chunks)

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        pass

    def as_retriever(self, top_k: Optional[int] = 4) -> EmbeddingRetriever:
        """
        Args:
            top_k:(Optional[int]), default 4
        Returns:
            EmbeddingRetriever
        """
        return EmbeddingRetriever(
            top_k=top_k, vector_store_connector=self._vector_store_connector
        )
