"""Text2Vector class."""

import asyncio
import logging
from typing import List

from tenacity import retry, stop_after_attempt, wait_fixed

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
        return await self._embed(text)

    async def batch_embed(
        self,
        texts: List[str],
        batch_size: int = 1,
    ) -> List[List[float]]:
        """Embed texts from graphs in batches.""" 
        vectors = []
        n_texts = len(texts)

        # Batch embedding
        for batch_idx in range(0, n_texts, batch_size):
            start_idx = batch_idx
            end_idx = min(start_idx + batch_size, n_texts)
            batch_texts = texts[start_idx:end_idx]

            # Create tasks
            embedding_tasks = [(self._embed(text)) for text in batch_texts]

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
                
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _embed(self, text: str) -> List:
        """Inner embed."""
        return await self.embedding_fn.aembed_query(text)
    
    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""
