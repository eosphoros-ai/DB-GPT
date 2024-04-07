"""DBSchemaAssembler."""
from typing import Any, List, Optional

from dbgpt.core import Chunk, Embeddings
from dbgpt.datasource.base import BaseConnector
from dbgpt.storage.vector_store.connector import VectorStoreConnector

from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters
from ..embedding.embedding_factory import DefaultEmbeddingFactory
from ..knowledge.datasource import DatasourceKnowledge
from ..retriever.db_schema import DBSchemaRetriever


class DBSchemaAssembler(BaseAssembler):
    """DBSchemaAssembler.

    Example:
        .. code-block:: python

            from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
            from dbgpt.serve.rag.assembler.db_struct import DBSchemaAssembler
            from dbgpt.storage.vector_store.connector import VectorStoreConnector
            from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig

            connection = SQLiteTempConnector.create_temporary_db()
            assembler = DBSchemaAssembler.load_from_connection(
                connector=connection,
                embedding_model=embedding_model_path,
            )
            assembler.persist()
            # get db struct retriever
            retriever = assembler.as_retriever(top_k=3)
    """

    def __init__(
        self,
        connector: BaseConnector,
        vector_store_connector: VectorStoreConnector,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.

        Args:
            connector: (BaseConnector) BaseConnector connection.
            vector_store_connector: (VectorStoreConnector) VectorStoreConnector to use.
            chunk_manager: (Optional[ChunkManager]) ChunkManager to use for chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
        """
        knowledge = DatasourceKnowledge(connector)
        self._connector = connector
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
    def load_from_connection(
        cls,
        connector: BaseConnector,
        vector_store_connector: VectorStoreConnector,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
    ) -> "DBSchemaAssembler":
        """Load document embedding into vector store from path.

        Args:
            connector: (BaseConnector) BaseConnector connection.
            vector_store_connector: (VectorStoreConnector) VectorStoreConnector to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
        Returns:
             DBSchemaAssembler
        """
        return cls(
            connector=connector,
            vector_store_connector=vector_store_connector,
            embedding_model=embedding_model,
            chunk_parameters=chunk_parameters,
            embeddings=embeddings,
        )

    def get_chunks(self) -> List[Chunk]:
        """Return chunk ids."""
        return self._chunks

    def persist(self) -> List[str]:
        """Persist chunks into vector store.

        Returns:
            List[str]: List of chunk ids.
        """
        return self._vector_store_connector.load_document(self._chunks)

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        return []

    def as_retriever(self, top_k: int = 4, **kwargs) -> DBSchemaRetriever:
        """Create DBSchemaRetriever.

        Args:
            top_k(int): default 4.

        Returns:
            DBSchemaRetriever
        """
        return DBSchemaRetriever(
            top_k=top_k,
            connector=self._connector,
            is_embeddings=True,
            vector_store_connector=self._vector_store_connector,
        )
