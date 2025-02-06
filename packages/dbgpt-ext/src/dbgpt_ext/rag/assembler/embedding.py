"""Embedding Assembler."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional

from dbgpt.core import Chunk, Embeddings
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.retriever import BaseRetriever, RetrieverStrategy
from dbgpt.rag.retriever.embedding import EmbeddingRetriever
from dbgpt.storage.base import IndexStoreBase
from dbgpt.util.executor_utils import blocking_func_to_async

from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters


class EmbeddingAssembler(BaseAssembler):
    """Embedding Assembler.

    Example:
    .. code-block:: python

        from dbgpt_ext.rag.assembler import EmbeddingAssembler

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
        index_store: IndexStoreBase,
        chunk_parameters: Optional[ChunkParameters] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.EMBEDDING,
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            index_store: (IndexStoreBase) IndexStoreBase to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            keyword_store: (Optional[IndexStoreBase]) IndexStoreBase to use.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
        """
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")
        self._index_store = index_store
        self._retrieve_strategy = retrieve_strategy

        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: Knowledge,
        index_store: IndexStoreBase,
        chunk_parameters: Optional[ChunkParameters] = None,
        embedding_model: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.EMBEDDING,
    ) -> "EmbeddingAssembler":
        """Load document embedding into vector store from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            index_store: (IndexStoreBase) IndexStoreBase to use.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            embedding_model: (Optional[str]) Embedding model to use.
            embeddings: (Optional[Embeddings]) Embeddings to use.
            retrieve_strategy: (Optional[RetrieverStrategy]) Retriever strategy.

        Returns:
             EmbeddingAssembler
        """
        return cls(
            knowledge=knowledge,
            index_store=index_store,
            chunk_parameters=chunk_parameters,
            embedding_model=embedding_model,
            embeddings=embeddings,
            retrieve_strategy=retrieve_strategy,
        )

    @classmethod
    async def aload_from_knowledge(
        cls,
        knowledge: Knowledge,
        index_store: IndexStoreBase,
        chunk_parameters: Optional[ChunkParameters] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.EMBEDDING,
    ) -> "EmbeddingAssembler":
        """Load document embedding into vector store from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            index_store: (IndexStoreBase) Index store to use.
            executor: (Optional[ThreadPoolExecutor) ThreadPoolExecutor to use.
            retrieve_strategy: (Optional[RetrieverStrategy]) Retriever strategy.

        Returns:
             EmbeddingAssembler
        """
        executor = executor or ThreadPoolExecutor()
        return await blocking_func_to_async(
            executor,
            cls,
            knowledge,
            index_store,
            chunk_parameters,
            retrieve_strategy,
        )

    def persist(self, **kwargs) -> List[str]:
        """Persist chunks into store.

        Returns:
            List[str]: List of chunk ids.
        """
        max_chunks_once_load = kwargs.get("max_chunks_once_load", 10)
        max_threads = kwargs.get("max_threads", 1)
        return self._index_store.load_document_with_limit(
            self._chunks, max_chunks_once_load, max_threads
        )

    async def apersist(self, **kwargs) -> List[str]:
        """Persist chunks into store.

        Returns:
            List[str]: List of chunk ids.
        """
        # persist chunks into vector store
        max_chunks_once_load = kwargs.get("max_chunks_once_load", 10)
        max_threads = kwargs.get("max_threads", 1)
        return await self._index_store.aload_document_with_limit(
            self._chunks, max_chunks_once_load, max_threads
        )

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        return []

    def as_retriever(self, top_k: int = 4, **kwargs) -> BaseRetriever:
        """Create a retriever.

        Args:
            top_k(int): default 4.

        Returns:
            EmbeddingRetriever
        """
        return EmbeddingRetriever(
            top_k=top_k,
            index_store=self._index_store,
            retrieve_strategy=self._retrieve_strategy,
        )
