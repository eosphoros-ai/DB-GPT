from abc import ABC, abstractmethod
from typing import List

from dbgpt.core import LLMClient
from dbgpt.rag.chunk import Chunk


class Extractor(ABC):
    """Extractor Base class, it's apply for Summary Extractor, Keyword Extractor, Triplets Extractor, Question Extractor, etc."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the Extractor."""
        self._llm_client = llm_client

    def extract(self, chunks: List[Chunk]) -> str:
        """Extracts chunks.

        Args:
            chunks (List[Chunk]): extract metadata from chunks
        """
        return self._extract(chunks)

    async def aextract(self, chunks: List[Chunk]) -> str:
        """Async Extracts chunks.

        Args:
            chunks (List[Chunk]): extract metadata from chunks
        """
        return await self._aextract(chunks)

    @abstractmethod
    def _extract(self, chunks: List[Chunk]) -> str:
        """Extracts chunks.

        Args:
            chunks (List[Chunk]): extract metadata from chunks
        """

    @abstractmethod
    async def _aextract(self, chunks: List[Chunk]) -> str:
        """Async Extracts chunks.

        Args:
            chunks (List[Chunk]): extract metadata from chunks
        """
