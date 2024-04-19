"""Knowledge graph class."""
import logging

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase

logger = logging.getLogger(__name__)


class KnowledgeGraph(KnowledgeGraphBase):
    """Knowledge graph class."""

    def __init__(
        self,
        graph_store: GraphStoreBase
    ) -> None:
        """Create a KnowledgeGraph instance."""
        self.graph_store = graph_store
