"""Community metastore."""
import logging
from abc import ABC, abstractmethod
from typing import List

from dbgpt.storage.graph_store.community_store import Community

logger = logging.getLogger(__name__)


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
        """Upsert community."""

    @abstractmethod
    def drop(self):
        """Drop all communities."""
