"""Transformer base class."""
import logging
from abc import ABC

logger = logging.getLogger(__name__)


class TransformerBase(ABC):
    """Transformer base class."""


class EmbedderBase(TransformerBase, ABC):
    """Embedder base class."""


class ExtractorBase(TransformerBase, ABC):
    """Translator base class."""


class TranslatorBase(TransformerBase, ABC):
    """Translator base class."""
