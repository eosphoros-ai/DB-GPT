"""Embedding Assembler."""
from typing import Any, List, Optional

from dbgpt.core import Chunk, Embeddings
from dbgpt.storage.vector_store.connector import VectorStoreConnector

from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters
from ..embedding.embedding_factory import DefaultEmbeddingFactory
from ..knowledge.base import Knowledge
from ..retriever.embedding import EmbeddingRetriever


class EmbeddingAssembler(BaseAssembler):
    """Embedding Assembler.

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
        vector_store_connector: VectorStoreConnector,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            vector_store_connector: (VectorStoreConnector) VectorStoreConnector to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
        """
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")
        self._vector_store_connector = vector_store_connector

        self._embedding_model = embedding_model
        if self._embedding_model and not embeddings:
            embeddings = DefaultEmbeddingFactory(
                default_model_name=self._embedding_model
            ).create(self._embedding_model)

        if (
            embeddings
            and self._vector_store_connector.vector_store_config.embedding_fn is None
        ):
            self._vector_store_connector.vector_store_config.embedding_fn = embeddings

        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: Knowledge,
        vector_store_connector: VectorStoreConnector,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
    ) -> "EmbeddingAssembler":
        """Load document embedding into vector store from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            vector_store_connector: (VectorStoreConnector) VectorStoreConnector to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.

        Returns:
             EmbeddingAssembler
        """
        return cls(
            knowledge=knowledge,
            vector_store_connector=vector_store_connector,
            chunk_parameters=chunk_parameters,
            embedding_model=embedding_model,
            embeddings=embeddings,
        )

    def persist(self) -> List[str]:
        """Persist chunks into vector store.

        Returns:
            List[str]: List of chunk ids.
        """
        return self._vector_store_connector.load_document(self._chunks)

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        return []

    def as_retriever(self, top_k: int = 4, **kwargs) -> EmbeddingRetriever:
        """Create a retriever.

        Args:
            top_k(int): default 4.

        Returns:
            EmbeddingRetriever
        """
        return EmbeddingRetriever(
            top_k=top_k, vector_store_connector=self._vector_store_connector
        )
