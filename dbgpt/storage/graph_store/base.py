"""Graph store base class."""
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple

from dbgpt._private.pydantic import BaseModel
from dbgpt.storage.graph_store.graph import Direction, Graph

logger = logging.getLogger(__name__)


class GraphStoreConfig(BaseModel):
    """Graph store config."""


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
    def get_schema(self, refresh: bool = False) -> str:
        """Get schema."""

    @abstractmethod
    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = None,
        fan: int = None,
        limit: int = None,
    ) -> Graph:
        """Explore on graph."""

    @abstractmethod
    def query(self, query: str, **args) -> Graph:
        """Execute a query."""
