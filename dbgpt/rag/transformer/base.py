"""Transformer base class."""
import logging
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)


class TransformerBase(ABC):
    """Transformer base class."""


class EmbedderBase(TransformerBase, ABC):
    """Embedder base class."""


class ExtractorBase(TransformerBase, ABC):
    """Extractor base class."""

    @abstractmethod
    async def extract(
        self,
        text: str,
        limit: int = None
    ) -> List:
        """Extract results from text."""


class TranslatorBase(TransformerBase, ABC):
    """Translator base class."""
