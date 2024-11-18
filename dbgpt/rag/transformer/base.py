"""Transformer base class."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

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
