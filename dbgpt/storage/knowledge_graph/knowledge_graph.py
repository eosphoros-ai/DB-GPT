"""Knowledge graph class."""
import logging
from typing import Optional, List

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
        keyword_extractor: ExtractorBase
    ) -> None:
        """Create a KnowledgeGraph instance."""
        self.graph_store = graph_store
        self.extractor = triplet_extractor
        self.keyword_extractor = keyword_extractor

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        # extract chunk content to triplets
        triplets = set()
        for chunk in chunks:
            triplets += self.extractor.extract(chunk.content)

        # persist triplets
        for triplet in triplets:
            self.graph_store.insert_triplet(*triplet)

        return [chunk.chunk_id for chunk in chunks]

    def similar_search_with_scores(self, text, topk, score_threshold: float,
        filters: Optional[MetadataFilters] = None) -> List[Chunk]:
        # extract keywords from query text
        keywords = self.keyword_extractor.extract(text)

        # todo: async to sync
        self.graph_store.explore(keywords, result_limit=topk)
        pass
