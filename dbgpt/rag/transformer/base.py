"""Transformer base class."""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


class TransformerBase:
    """Transformer base class."""


class EmbedderBase(TransformerBase, ABC):
    """Embedder base class."""


class ExtractorBase(TransformerBase, ABC):
    """Extractor base class."""

    @abstractmethod
    async def extract(self, text: str, limit: Optional[int] = None) -> List:
        """Extract results from text."""


class TranslatorBase(TransformerBase, ABC):
    """Translator base class."""
