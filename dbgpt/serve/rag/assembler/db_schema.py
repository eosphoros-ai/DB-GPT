import os
from typing import Optional, Any, List

from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.chunk_manager import ChunkParameters, ChunkManager
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.knowledge.base import Knowledge, ChunkStrategy
from dbgpt.rag.knowledge.factory import KnowledgeFactory
from dbgpt.rag.retriever.db_schema import DBSchemaRetriever
from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary
from dbgpt.serve.rag.assembler.base import BaseAssembler
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class DBSchemaAssembler(BaseAssembler):
    """DBSchemaAssembler
    Example:
        .. code-block:: python

            from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnect
            from dbgpt.serve.rag.assembler.db_struct import DBSchemaAssembler
            from dbgpt.storage.vector_store.connector import VectorStoreConnector
            from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig

            connection = SQLiteTempConnect.create_temporary_db()
            assembler = DBSchemaAssembler.load_from_connection(
                connection=connection,
                embedding_model=embedding_model_path,
            )
            assembler.persist()
            # get db struct retriever
            retriever = assembler.as_retriever(top_k=3)
    """

    def __init__(
        self,
        connection: RDBMSDatabase = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embedding_factory: Optional[EmbeddingFactory] = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.
        Args:
            connection: (RDBMSDatabase) RDBMSDatabase connection.
            knowledge: (Knowledge) Knowledge datasource.
            chunk_manager: (Optional[ChunkManager]) ChunkManager to use for chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embedding_factory: (Optional[EmbeddingFactory]) EmbeddingFactory to use.
            vector_store_connector: (Optional[VectorStoreConnector]) VectorStoreConnector to use.
        """
        if connection is None:
            raise ValueError("datasource connection must be provided.")
        self._connection = connection
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
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_connection(
        cls,
        connection: RDBMSDatabase = None,
        knowledge: Optional[Knowledge] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embedding_factory: Optional[EmbeddingFactory] = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
    ) -> "DBSchemaAssembler":
        """Load document embedding into vector store from path.
        Args:
            connection: (RDBMSDatabase) RDBMSDatabase connection.
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embedding_factory: (Optional[EmbeddingFactory]) EmbeddingFactory to use.
            vector_store_connector: (Optional[VectorStoreConnector]) VectorStoreConnector to use.
        Returns:
             DBSchemaAssembler
        """
        embedding_factory = embedding_factory
        chunk_parameters = chunk_parameters or ChunkParameters(
            chunk_strategy=ChunkStrategy.CHUNK_BY_SIZE.name, chunk_overlap=0
        )

        return cls(
            connection=connection,
            knowledge=knowledge,
            embedding_model=embedding_model,
            chunk_parameters=chunk_parameters,
            embedding_factory=embedding_factory,
            vector_store_connector=vector_store_connector,
        )

    def load_knowledge(self, knowledge: Optional[Knowledge] = None) -> None:
        table_summaries = _parse_db_summary(self._connection)
        self._chunks = []
        self._knowledge = knowledge
        for table_summary in table_summaries:
            from dbgpt.rag.knowledge.base import KnowledgeType

            self._knowledge = KnowledgeFactory.from_text(
                text=table_summary, knowledge_type=KnowledgeType.DOCUMENT
            )
            self._chunk_parameters.chunk_size = len(table_summary)
            self._chunk_manager = ChunkManager(
                knowledge=self._knowledge, chunk_parameter=self._chunk_parameters
            )
            self._chunks.extend(self._chunk_manager.split(self._knowledge.load()))

    def get_chunks(self) -> List[Chunk]:
        """Return chunk ids."""
        return self._chunks

    def persist(self) -> List[str]:
        """Persist chunks into vector store."""
        return self._vector_store_connector.load_document(self._chunks)

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""

    def as_retriever(self, top_k: Optional[int] = 4) -> DBSchemaRetriever:
        """
        Args:
            top_k:(Optional[int]), default 4
        Returns:
            DBSchemaRetriever
        """
        return DBSchemaRetriever(
            top_k=top_k,
            connection=self._connection,
            is_embeddings=True,
            vector_store_connector=self._vector_store_connector,
        )
