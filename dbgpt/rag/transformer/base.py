"""Transformer base class."""
import logging
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)
limit_num = 10

class TransformerBase(ABC):
    """Transformer base class."""

    @abstractmethod
    def transform(self, data):
        """Transform the input data and return the result."""
        pass


class EmbedderBase(TransformerBase, ABC):
    """Embedder base class."""


class ExtractorBase(TransformerBase, ABC):
    """Extractor base class."""

    @abstractmethod
    async def extract(self, text: str, limit: int = limit_num) -> List:
        """Extract results from text."""


class TranslatorBase(TransformerBase, ABC):
    """Translator base class."""
