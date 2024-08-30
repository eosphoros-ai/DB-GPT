"""Define Classes about Community."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Graph

logger = logging.getLogger(__name__)


@dataclass
class Community:
    """Community class."""

    id: str
    data: Optional[Graph] = None
    summary: Optional[str] = None


@dataclass
class CommunityTree:
    """Represents a community tree."""


class CommunityStoreAdapter(ABC):
    """Community Store Adapter."""

    def __init__(self, graph_store: GraphStoreBase):
        """Initialize Community Store Adapter."""
        self._graph_store = graph_store

    @property
    def graph_store(self) -> GraphStoreBase:
        """Get graph store."""
        return self._graph_store

    @abstractmethod
    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery."""

    @abstractmethod
    async def get_community(self, community_id: str) -> Community:
        """Get community."""


class CommunityMetastore(ABC):
    """Community metastore class."""

    @abstractmethod
    def get(self, community_id: str) -> Community:
        """Get community."""

    @abstractmethod
    def list(self) -> List[Community]:
        """Get all communities."""

    @abstractmethod
    async def search(self, query: str) -> List[Community]:
        """Search communities relevant to query."""

    @abstractmethod
    async def save(self, communities: List[Community]):
        """Save communities."""

    @abstractmethod
    async def truncate(self):
        """Truncate all communities."""

    @abstractmethod
    def drop(self):
        """Drop community metastore."""
