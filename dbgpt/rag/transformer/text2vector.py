"""Text2Vector class."""

import logging
from typing import List

from dbgpt.core.interface.embeddings import Embeddings
from dbgpt.rag.transformer.base import EmbedderBase

logger = logging.getLogger(__name__)


class Text2Vector(EmbedderBase):
    """Text2Vector class."""

    def __init__(self, embedding_fn: Embeddings):
        """Initialize the Embedder."""
        self.embedding_fn = embedding_fn
        super().__init__()

    async def embed(self, text: str) -> List[float]:
        """Embed vector from text."""
        return await self.embedding_fn.aembed_query(text)

    async def batch_embed(
        self,
        text_list: List[List],
        batch_size: int = 1,
    ) -> List[List[float]]:
        """Embed texts from graphs in batches."""

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""
