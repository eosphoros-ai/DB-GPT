"""Community metastore."""
import logging
from abc import ABC, abstractmethod
from typing import List

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.community_store import Community

logger = logging.getLogger(__name__)


class CommunityStoreAdapter(ABC):
    """Community Store Adapter."""

    def __init__(self, graph_store: GraphStoreBase):
        self._graph_store = graph_store

    @property
    def graph_store(self) -> GraphStoreBase:
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
        """get all communities."""

    @abstractmethod
    async def search(self, query: str) -> List[Community]:
        """search communities relevant to query."""

    @abstractmethod
    async def save(self, communities: List[Community]):
        """Save communities."""

    @abstractmethod
    def truncate(self):
        """Truncate all communities."""

    @abstractmethod
    def drop(self):
        """Drop community metastore."""
