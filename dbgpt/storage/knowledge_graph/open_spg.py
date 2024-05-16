"""OpenSPG class."""
import logging
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.storage.graph_store.graph import Graph, MemoryGraph
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase, KnowledgeGraphConfig
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class OpenSPGConfig(KnowledgeGraphConfig):
    """OpenSPG config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OpenSPG(KnowledgeGraphBase):
    """OpenSPG class."""

    # todo: add OpenSPG implementation

    def __init__(self, config: OpenSPGConfig):
        """Initialize the OpenSPG with config details."""
        pass

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document."""
        return []

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Similar with scores."""
        return []

    def query_graph(self, limit: Optional[int] = None) -> Graph:
        """Query graph."""
        return MemoryGraph()

    def delete_vector_name(self, index_name: str):
        """Delete vector name."""
        pass
