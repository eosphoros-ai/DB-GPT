"""Text2Vector class."""

import logging
import dashscope
from http import HTTPStatus
from abc import ABC
from typing import List

from dbgpt.rag.transformer.base import EmbedderBase

logger = logging.getLogger(__name__)


class Text2Vector(EmbedderBase, ABC):
    """Text2Vector class."""

    def __init__(self):
        """Initialize the Embedder"""

    async def embed(self, text: str) -> List[float]:
        """Embed vector from text."""
        return await self._embed(text)

    async def batch_embed(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """Batch embed vectors from texts."""
        results = []
        for text in texts:
            vector = self._embed(text)
            results.extend(vector)
        return results

    async def _embed(self, text: str) -> List[float]:
        """Embed vector from text."""
        resp = dashscope.TextEmbedding.call(
            model = dashscope.TextEmbedding.Models.text_embedding_v1,
            input = text)
        if resp.status_code == HTTPStatus.OK:
            return list(resp.embeddings.embedding)
        else:
            return list(resp.embeddings.embedding)

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""