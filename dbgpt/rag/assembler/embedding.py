"""Embedding Assembler."""
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional

from dbgpt.core import Chunk, Embeddings

from ...util.executor_utils import blocking_func_to_async
from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters
from ..index.base import IndexStoreBase
from ..knowledge.base import Knowledge
from ..retriever import BaseRetriever, RetrieverStrategy
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

    def persist(self) -> List[str]:
        """Persist chunks into store.

        Returns:
            List[str]: List of chunk ids.
        """
        return self._index_store.load_document(self._chunks)

    async def apersist(self) -> List[str]:
        """Persist chunks into store.

        Returns:
            List[str]: List of chunk ids.
        """
        # persist chunks into vector store
        return await self._index_store.aload_document(self._chunks)

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
