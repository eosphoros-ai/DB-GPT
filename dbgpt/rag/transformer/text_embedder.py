"""TextEmbedder class."""

import asyncio
import logging
from typing import List

from dbgpt.core.interface.embeddings import Embeddings
from dbgpt.rag.transformer.base import EmbedderBase

logger = logging.getLogger(__name__)


class TextEmbedder(EmbedderBase):
    """TextEmbedder class."""

    def __init__(self, embedding_fn: Embeddings):
        """Initialize the Embedder."""
        super().__init__(embedding_fn)

    async def embed(self, input: str) -> List[float]:
        """Embed vector from text."""
        return await super().embed(input)

    async def batch_embed(
        self,
        inputs: List[str],
        batch_size: int = 1,
    ) -> List[List[float]]:
        """Embed texts from graphs in batches."""
        vectors = []
        n_texts = len(inputs)

        # Batch embedding
        for batch_idx in range(0, n_texts, batch_size):
            start_idx = batch_idx
            end_idx = min(start_idx + batch_size, n_texts)
            batch_texts = inputs[start_idx:end_idx]

            # Create tasks
            embedding_tasks = [(self.embed(text)) for text in batch_texts]

            # Process embedding in parallel
            batch_results = await asyncio.gather(
                *(task for task in embedding_tasks), return_exceptions=True
            )

            # Place results in the correct positions
            for idx, vector in enumerate(batch_results):
                if isinstance(vector, Exception):
                    raise RuntimeError(f"Failed to embed text{idx}")
                else:
                    vectors.append(vector)

        return vectors

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""
