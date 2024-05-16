"""Graph store base class."""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import Embeddings
from dbgpt.storage.graph_store.graph import Direction, Graph

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


class GraphStoreBase(ABC):
    """Graph store base class."""

    @abstractmethod
    def insert_triplet(self, sub: str, rel: str, obj: str):
        """Add triplet."""

    @abstractmethod
    def get_triplets(self, sub: str) -> List[Tuple[str, str]]:
        """Get triplets."""

    @abstractmethod
    def delete_triplet(self, sub: str, rel: str, obj: str):
        """Delete triplet."""

    @abstractmethod
    def drop(self):
        """Drop graph."""

    @abstractmethod
    def get_schema(self, refresh: bool = False) -> str:
        """Get schema."""

    @abstractmethod
    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Get full graph."""

    @abstractmethod
    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: Optional[int] = None,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Graph:
        """Explore on graph."""

    @abstractmethod
    def query(self, query: str, **args) -> Graph:
        """Execute a query."""
