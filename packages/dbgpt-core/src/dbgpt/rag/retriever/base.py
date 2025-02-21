"""Base retriever module."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from dbgpt.core import Chunk
from dbgpt.storage.vector_store.filters import MetadataFilters


class RetrieverStrategy(str, Enum):
    """Retriever strategy.

    Args:
        - EMBEDDING: embedding retriever
        - KEYWORD: keyword retriever
        - HYBRID: hybrid retriever
    """

    EMBEDDING = "embedding"
    GRAPH = "graph"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class BaseRetriever(ABC):
    """Base retriever."""

    def load_document(self, chunks: List[Chunk], **kwargs: Dict[str, Any]) -> List[str]:
        """Load document in vector database.

        Args:
            - chunks: document chunks.
        Return chunk ids.
        """
        raise NotImplementedError

    def retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: (Optional[MetadataFilters]) metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """
        return self._retrieve(query, filters)

    async def aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): async query text.
            filters: (Optional[MetadataFilters]) metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """
        return await self._aretrieve(query, filters)

    def retrieve_with_scores(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text.
            score_threshold (float): score threshold.
            filters: (Optional[MetadataFilters]) metadata filters.


        Returns:
            List[Chunk]: list of chunks
        """
        return self._retrieve_with_score(query, score_threshold, filters)

    async def aretrieve_with_scores(
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

        Returns:
            List[Chunk]: list of chunks
        """
        return await self._aretrieve_with_score(query, score_threshold, filters)

    @abstractmethod
    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: (Optional[MetadataFilters]) metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """

    @abstractmethod
    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Async Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: (Optional[MetadataFilters]) metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """

    @abstractmethod
    def _retrieve_with_score(
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

        Returns:
            List[Chunk]: list of chunks
        """

    @abstractmethod
    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Async Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: (Optional[MetadataFilters]) metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """

    @classmethod
    def name(cls):
        """Return the name of the retriever."""
        raise NotImplementedError("Current retriever does not support name")
