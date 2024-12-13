"""Text2Vector class."""

import logging
from abc import ABC
from http import HTTPStatus
from typing import List

import dashscope

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
            vector = await self._embed(text)
            results.extend(vector)
        return results

    async def _embed(self, text: str) -> List[float]:
        """Embed vector from text."""
        resp = dashscope.TextEmbedding.call(
            model = dashscope.TextEmbedding.Models.text_embedding_v3,
            input = text,
            dimension = 512)
        embeddings = resp.output['embeddings']
        embedding = embeddings[0]['embedding']
        return list(embedding)

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""
