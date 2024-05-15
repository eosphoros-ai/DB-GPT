"""OpenSPG class."""
import logging
from typing import Optional, List

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.storage.graph_store.graph import Graph
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase, \
    KnowledgeGraphConfig
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class OpenSPGConfig(KnowledgeGraphConfig):
    """OpenSPG config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OpenSPG(KnowledgeGraphBase):
    """OpenSPG class."""

    # todo: add OpenSPG implementation

    def __init__(self, config: OpenSPGConfig):
        pass

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        pass

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        pass

    def query_graph(self, limit: int = None) -> Graph:
        pass

    def delete_vector_name(self, index_name: str):
        pass
