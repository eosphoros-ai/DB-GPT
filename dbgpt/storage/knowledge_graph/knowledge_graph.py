"""Knowledge graph class."""
import asyncio
import logging
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.transformer.base import ExtractorBase
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class KnowledgeGraph(KnowledgeGraphBase):
    """Knowledge graph class."""

    def __init__(
        self,
        graph_store: GraphStoreBase,
        triplet_extractor: ExtractorBase,
        keyword_extractor: ExtractorBase,
    ) -> None:
        """Create a KnowledgeGraph instance."""
        self._graph_store = graph_store
        self._triplet_extractor = triplet_extractor
        self._keyword_extractor = keyword_extractor

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist triplets to graph store."""

        async def process_chunk(chunk):
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                self._graph_store.insert_triplet(*triplet)
            return chunk.chunk_id

        # wait async tasks completed
        tasks = [process_chunk(chunk) for chunk in chunks]
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(asyncio.gather(*tasks))

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search for similar items based on text and returns chunks with scores."""
        if not filters:
            raise ValueError("Filters on knowledge graph not supported yet")

        # extract keywords and explore graph store
        async def process_query(query):
            keywords = await self._keyword_extractor.extract(query)
            subgraph = self._graph_store.explore(keywords, limit=topk)
            return [Chunk(content=subgraph.format(), metadata=subgraph.schema())]

        # wait async task completed
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(asyncio.gather(*[process_query(text)]))
