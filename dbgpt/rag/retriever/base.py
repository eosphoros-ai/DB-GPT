"""Base retriever module."""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from dbgpt.core import Chunk


class RetrieverStrategy(str, Enum):
    """Retriever strategy.

    Args:
        - EMBEDDING: embedding retriever
        - KEYWORD: keyword retriever
        - HYBRID: hybrid retriever
    """

    EMBEDDING = "embedding"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class BaseRetriever(ABC):
    """Base retriever."""

    def retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text

        Returns:
            List[Chunk]: list of chunks
        """
        return self._retrieve(query)

    async def aretrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): async query text

        Returns:
            List[Chunk]: list of chunks
        """
        return await self._aretrieve(query)

    def retrieve_with_scores(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Returns:
            List[Chunk]: list of chunks
        """
        return self._retrieve_with_score(query, score_threshold)

    async def aretrieve_with_scores(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Returns:
            List[Chunk]: list of chunks
        """
        return await self._aretrieve_with_score(query, score_threshold)

    @abstractmethod
    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text

        Returns:
            List[Chunk]: list of chunks
        """

    @abstractmethod
    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Async Retrieve knowledge chunks.

        Args:
            query (str): query text

        Returns:
            List[Chunk]: list of chunks
        """

    @abstractmethod
    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Returns:
            List[Chunk]: list of chunks
        """

    @abstractmethod
    async def _aretrieve_with_score(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Async Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Returns:
            List[Chunk]: list of chunks
        """
