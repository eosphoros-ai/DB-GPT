"""Community metastore."""
import logging
import os
from abc import ABC, abstractmethod
from typing import List

from dbgpt.core import Chunk
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.storage.graph_store.community_store import Community
from dbgpt.storage.knowledge_graph.community_summary import \
    CommunitySummaryKnowledgeGraphConfig
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.factory import VectorStoreFactory

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
    def save(self, communities: List[Community]):
        """Upsert community."""

    @abstractmethod
    def drop(self):
        """Drop all communities."""


class BuiltinCommunityMetastore(CommunityMetastore):
    """Builtin Community metastore."""

    VECTOR_SPACE_SUFFIX = "_COMMUNITY_SUMMARY"

    def __init__(
        self,
        config: CommunitySummaryKnowledgeGraphConfig,
        rdb_store: RDBMSConnector = None
    ):
        self._vector_store_type = (
            os.getenv("VECTOR_STORE_TYPE") or config.vector_store_type
        )
        self._vector_space = config.name + self.VECTOR_SPACE_SUFFIX
        self._max_chunks_once_load = config.max_chunks_once_load
        self._max_threads = config.max_threads
        self._topk = (
            os.getenv("KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_TOP_SIZE")
            or config.community_topk
        )
        self._score_threshold = (
            os.getenv("KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_RECALL_SCORE")
            or config.community_score_threshold
        )

        def configure(cfg: VectorStoreConfig):
            cfg.name = self._vector_space
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password

        self._vector_store = VectorStoreFactory.create(
            self._vector_store_type, configure
        )
        self._rdb_store = rdb_store

    def get(self, community_id: str) -> Community:
        """Get community."""
        raise NotImplementedError("Get community not allowed")

    def list(self) -> List[Community]:
        """get all communities."""
        raise NotImplementedError("List communities not allowed")

    async def search(self, query: str) -> List[Community]:
        """search communities relevant to query."""
        chunks = await self._vector_store.asimilar_search_with_scores(
            query,
            self._topk,
            self._score_threshold,
        )
        return [
            Community(id=chunk.id, summary=chunk.content) for chunk in chunks
        ]

    def save(self, communities: List[Community]):
        """Upsert communities."""
        chunks = [Chunk(id=c.id, content=c.summary) for c in communities]
        self._vector_store.aload_document_with_limit(
            chunks, self._max_chunks_once_load, self._max_threads
        )
        logger.info(f"Save {len(communities)} communities")

    def drop(self):
        self._vector_store.delete_vector_name(self._vector_space)
