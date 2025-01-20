"""GraphEmbedder class."""

import asyncio
import logging
from typing import List

from dbgpt.rag.transformer.base import EmbedderBase
from dbgpt.storage.graph_store.graph import Graph, GraphElemType

logger = logging.getLogger(__name__)


class GraphEmbedder(EmbedderBase):
    """GraphEmbedder class."""

    async def batch_embed(
        self,
        inputs: List[Graph],
        batch_size: int = 1,
    ) -> List[Graph]:
        """Embed graph from graphs in batches."""
        for graph in inputs:
            texts = []
            vectors = []

            # Get the text from graph
            for vertex in graph.vertices():
                if vertex.get_prop("vertex_type") == GraphElemType.CHUNK.value:
                    texts.append(vertex.get_prop("content"))
                elif vertex.get_prop("vertex_type") == GraphElemType.ENTITY.value:
                    texts.append(vertex.vid)
                else:
                    texts.append(" ")

            n_texts = len(texts)

            # Batch embedding
            for batch_idx in range(0, n_texts, batch_size):
                start_idx = batch_idx
                end_idx = min(start_idx + batch_size, n_texts)
                batch_texts = texts[start_idx:end_idx]

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
                    vectors.append(vector)

            # Push vectors back into Graph
            for vertex, vector in zip(graph.vertices(), vectors):
                vertex.set_prop("_embedding", vector)

        return inputs

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""
