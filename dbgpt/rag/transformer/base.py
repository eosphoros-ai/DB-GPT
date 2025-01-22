"""Transformer base class."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_fixed

from dbgpt.core.interface.embeddings import Embeddings

logger = logging.getLogger(__name__)


class TransformerBase:
    """Transformer base class."""

    @abstractmethod
    def truncate(self):
        """Truncate operation."""

    @abstractmethod
    def drop(self):
        """Clean operation."""


class EmbedderBase(TransformerBase, ABC):
    """Embedder base class."""

    def __init__(self, embedding_fn: Optional[Embeddings]):
        """Initialize the Embedder."""
        if not embedding_fn:
            raise ValueError("Embedding sevice is required.")
        self._embedding_fn = embedding_fn

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def embed(self, text: str) -> List[float]:
        """Embed vector from text."""
        return await self._embedding_fn.aembed_query(text=text)

    @abstractmethod
    async def batch_embed(
        self,
        inputs: List,
        batch_size: int = 1,
    ) -> List:
        """Batch embed vectors from texts."""


class SummarizerBase(TransformerBase, ABC):
    """Summarizer base class."""

    @abstractmethod
    async def summarize(self, **args) -> str:
        """Summarize result."""


class ExtractorBase(TransformerBase, ABC):
    """Extractor base class."""

    @abstractmethod
    async def extract(self, text: str, limit: Optional[int] = None) -> List:
        """Extract results from text."""

    @abstractmethod
    async def batch_extract(
        self,
        texts: List[str],
        batch_size: int = 1,
        limit: Optional[int] = None,
    ) -> List:
        """Batch extract results from texts."""


class TranslatorBase(TransformerBase, ABC):
    """Translator base class."""

    @abstractmethod
    async def translate(self, text: str) -> Dict:
        """Translate results from text."""
