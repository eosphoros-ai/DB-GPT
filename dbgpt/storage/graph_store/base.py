"""Graph store base class."""

import logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import Embeddings
from dbgpt.storage.graph_store.graph import MemoryGraph, Vertex

logger = logging.getLogger(__name__)


class GraphStoreConfig(BaseModel):
    """Graph store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(
        default="dbgpt_collection",
        description="The name of graph store, inherit from index store.",
    )
    embedding_fn: Optional[Embeddings] = Field(
        default=None,
        description="The embedding function of graph store, optional.",
    )
    summary_enabled: bool = Field(
        default=False,
        description="Enable graph community summary or not.",
    )


class GraphStoreBase(ABC):
    """Graph store base class."""

    def __init__(self, config: GraphStoreConfig):
        """Initialize graph store."""
        self._config = config
        self.conn = None

    @abstractmethod
    def get_config(self) -> GraphStoreConfig:
        """Get the graph store config."""

    @abstractmethod
    def _escape_quotes(self, text: str) -> str:
        """Escape single and double quotes in a string for queries."""

    @abstractmethod
    def _paser(self, entities: List[Vertex]) -> str:
        """Parse entities to string."""

    @abstractmethod
    def query(self, query: str, **kwargs) -> MemoryGraph:
        """Execute a query on graph."""

    @abstractmethod
    async def stream_query(self, query: str, **kwargs) -> AsyncGenerator[Graph, None]:
        """Execute a stream query."""
