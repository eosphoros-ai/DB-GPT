from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Tuple
from dbgpt.rag.chunk import Chunk


class RetrieverMode(str, Enum):
    """Retriever mode.
    Args:
        - KEYWORD: keyword retriever
        - EMBEDDING: embedding retriever
        - HYBRID: hybrid retriever
    """

    KEYWORD = "keyword"
    EMBEDDING = "embedding"
    HYBRID = "hybrid"


class BaseRetriever(ABC):
    """Base retriever."""

    def retrieve(self, query: str) -> List[Chunk]:
        """
        Args:
            query (str): query text
        """
        return self._retrieve(query)

    async def aretrieve(self, query: str) -> List[Chunk]:
        """
        Args:
            query (str): async query text
        """
        return await self._aretrieve(query)

    def retrieve_with_scores(self, query: str, score_threshold: float) -> List[Chunk]:
        """
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
        return self._retrieve_with_score(query, score_threshold)

    async def aretrieve_with_scores(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
        return await self._aretrieve_with_score(query, score_threshold)

    @abstractmethod
    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
        """

    @abstractmethod
    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Async Retrieve knowledge chunks.
        Args:
            query (str): query text
        """

    @abstractmethod
    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """

    @abstractmethod
    async def _aretrieve_with_score(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Async Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
        """
