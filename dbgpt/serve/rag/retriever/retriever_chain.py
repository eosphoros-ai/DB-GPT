from concurrent.futures import Executor, ThreadPoolExecutor
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import blocking_func_to_async


class RetrieverChain(BaseRetriever):
    """Retriever chain class."""

    def __init__(
        self,
        retrievers: Optional[List[BaseRetriever]] = None,
        executor: Optional[Executor] = None,
    ):
        """Create retriever chain instance."""
        self._retrievers = retrievers or []
        self._executor = executor or ThreadPoolExecutor()

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        for retriever in self._retrievers:
            candidates = retriever.retrieve(query, filters)
            if candidates:
                return candidates
        return []

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        candidates = await blocking_func_to_async(
            self._executor, self._retrieve, query, filters
        )
        return candidates

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        for retriever in self._retrievers:
            candidates_with_scores = retriever.retrieve_with_scores(
                query=query, score_threshold=score_threshold, filters=filters
            )
            if candidates_with_scores:
                return candidates_with_scores
        return []

    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        candidates_with_score = await blocking_func_to_async(
            self._executor, self._retrieve_with_score, query, score_threshold, filters
        )
        return candidates_with_score
