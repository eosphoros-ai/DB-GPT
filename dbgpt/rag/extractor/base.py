"""Base Extractor Base class."""
from abc import ABC, abstractmethod
from typing import List

from dbgpt.core import Chunk, LLMClient


class Extractor(ABC):
    """Base Extractor Base class.

    It's apply for Summary Extractor, Keyword Extractor, Triplets Extractor, Question
    Extractor, etc.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the Extractor."""
        self._llm_client = llm_client

    def extract(self, chunks: List[Chunk]) -> str:
        """Return extracted metadata from chunks.

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
        """Return extracted metadata from chunks.

        Args:
            chunks (List[Chunk]): extract metadata from chunks
        """

    @abstractmethod
    async def _aextract(self, chunks: List[Chunk]) -> str:
        """Async Extracts chunks.

        Args:
            chunks (List[Chunk]): extract metadata from chunks
        """
