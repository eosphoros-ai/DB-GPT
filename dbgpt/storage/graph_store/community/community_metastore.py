"""Community metastore."""
from abc import ABC, abstractmethod
from typing import List

from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.storage.graph_store.community_store import Community
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.storage.vector_store.pgvector_store import PGVectorStore


class CommunityMetastore(ABC):
    """Community metastore class."""

    @abstractmethod
    def get(self, community_id: str) -> Community:
        """Get community."""

    @abstractmethod
    def search(self, query: str) -> List[Community]:
        """search communities relevant to query."""

    @abstractmethod
    def save(self, community: Community):
        """Upsert community."""

    @abstractmethod
    def drop(self, community_id: str):
        """Drop community."""


class BuiltinCommunityMetastore(CommunityMetastore):
    rdb: RDBMSConnector

    vb: VectorStoreBase


class PGVectorCommunityMetastore(CommunityMetastore):
    """Community metastore with vector storage."""

    pg: PGVectorStore
