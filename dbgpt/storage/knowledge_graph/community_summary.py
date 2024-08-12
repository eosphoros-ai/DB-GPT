"""Define the CommunitySummaryKnowledgeGraph class inheriting from BuiltinKnowledgeGraph."""

import logging
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.rag.transformer.summary_triplet_extractor import \
    SummaryTripletExtractor
from dbgpt.storage.graph_store.community_store import CommunityStore
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class CommunitySummaryKnowledgeGraphConfig(BuiltinKnowledgeGraphConfig):
    """Community summary knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CommunitySummaryKnowledgeGraph(BuiltinKnowledgeGraph):
    """Community summary knowledge graph class."""

    def __init__(self, config: CommunitySummaryKnowledgeGraphConfig):
        super().__init__(config)

        self._triplet_extractor = SummaryTripletExtractor(self._llm_client, self._model_name)

        # Initialize CommunityStore with a graph storage instance
        self.community_store = CommunityStore(self._graph_store)

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        return await super().aload_document(chunks)

        # Load documents as chunks
        for chunk in chunks:
            # Extract triplets from each chunk
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                # Insert each triplet into the graph store
                self._graph_store.insert_triplet(*triplet)
            logger.info(
                f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
        # Build communities after loading all triplets
        self.community_store.build_communities()
        return [chunk.chunk_id for chunk in chunks]

    async def asimilar_search_with_scores(
        self,
        query,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        return await super().asimilar_search_with_scores(query, topk, score_threshold, filters)

        # Determine if search is global or local
        is_global_search = await self.get_intent_from_query(query)
        if is_global_search:
            return await self._global_search(query, topk, score_threshold,
                                             filters)
        else:
            return await self._local_search(query, topk, score_threshold,
                                            filters)

    async def _global_search(
        self,
        query,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        pass

    async def _local_search(
        self,
        query,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        pass

    async def _generate_answer_from_summary(self, community_summary, query):
        pass

    async def _aggregate_answers(self, community_answers):
        pass

    @staticmethod
    async def get_intent_from_query(query: str) -> bool:
        pass
