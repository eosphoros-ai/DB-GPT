"""DBSchemaAssembler."""

from typing import Any, List, Optional

from dbgpt.core import Chunk, Embeddings
from dbgpt.datasource.base import BaseConnector
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory
from dbgpt.storage.vector_store.base import VectorStoreBase

from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters
from ..knowledge.datasource import DatasourceKnowledge
from ..retriever.db_schema import DBSchemaRetriever


class DBSchemaAssembler(BaseAssembler):
    """DBSchemaAssembler.

    Example:
        .. code-block:: python

            from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector
            from dbgpt_serve.rag.assembler.db_struct import DBSchemaAssembler
            from dbgpt.storage.vector_store.connector import VectorStoreBase
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
        table_vector_store_connector: VectorStoreBase,
        field_vector_store_connector: Optional[VectorStoreBase] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        max_seq_length: int = 512,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.

        Args:
            connector: (BaseConnector) BaseConnector connection.
            table_vector_store_connector: VectorStoreConnector to load
                                        and retrieve table info.
            field_vector_store_connector: VectorStoreConnector to load
                                        and retrieve field info.
            chunk_manager: (Optional[ChunkManager]) ChunkManager to use for chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
        """
        self._connector = connector
        self._table_vector_store_connector = table_vector_store_connector
        self._field_vector_store_connector = field_vector_store_connector
        self._embedding_model = embedding_model
        if self._embedding_model and not embeddings:
            embeddings = DefaultEmbeddingFactory(
                default_model_name=self._embedding_model
            ).create(self._embedding_model)

        knowledge = DatasourceKnowledge(connector, model_dimension=max_seq_length)
        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_connection(
        cls,
        connector: BaseConnector,
        table_vector_store_connector: VectorStoreBase,
        field_vector_store_connector: Optional[VectorStoreBase] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        max_seq_length: int = 512,
    ) -> "DBSchemaAssembler":
        """Load document embedding into vector store from path.

        Args:
            connector: (BaseConnector) BaseConnector connection.
            table_vector_store_connector: used to load table chunks.
            field_vector_store_connector: used to load field chunks
                                        if field in table is too much.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
            max_seq_length: Embedding model max sequence length
        Returns:
             DBSchemaAssembler
        """
        return cls(
            connector=connector,
            table_vector_store_connector=table_vector_store_connector,
            field_vector_store_connector=field_vector_store_connector,
            embedding_model=embedding_model,
            chunk_parameters=chunk_parameters,
            embeddings=embeddings,
            max_seq_length=max_seq_length,
        )

    def get_chunks(self) -> List[Chunk]:
        """Return chunk ids."""
        return self._chunks

    def persist(self, **kwargs: Any) -> List[str]:
        """Persist chunks into vector store.

        Returns:
            List[str]: List of chunk ids.
        """
        table_chunks, field_chunks = [], []
        for chunk in self._chunks:
            metadata = chunk.metadata
            if metadata.get("separated"):
                if metadata.get("part") == "table":
                    table_chunks.append(chunk)
                else:
                    field_chunks.append(chunk)
            else:
                table_chunks.append(chunk)

        if self._field_vector_store_connector and field_chunks:
            self._field_vector_store_connector.load_document_with_limit(field_chunks)
        return self._table_vector_store_connector.load_document_with_limit(table_chunks)

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
            table_vector_store_connector=self._table_vector_store_connector,
            field_vector_store_connector=self._field_vector_store_connector,
        )
