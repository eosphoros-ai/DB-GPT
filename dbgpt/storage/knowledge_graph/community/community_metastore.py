"""Builtin Community metastore."""
import logging
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.storage.knowledge_graph.community.base import Community, CommunityMetastore
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)


class BuiltinCommunityMetastore(CommunityMetastore):
    """Builtin Community metastore."""

    def __init__(
        self, vector_store: VectorStoreBase, rdb_store: Optional[RDBMSConnector] = None
    ):
        """Initialize Community metastore."""
        self._vector_store = vector_store
        self._rdb_store = rdb_store

        config = self._vector_store.get_config()
        self._vector_space = config.name
        self._max_chunks_once_load = config.max_chunks_once_load
        self._max_threads = config.max_threads
        self._topk = config.topk
        self._score_threshold = config.score_threshold

    def get(self, community_id: str) -> Community:
        """Get community."""
        raise NotImplementedError("Get community not allowed")

    def list(self) -> List[Community]:
        """Get all communities."""
        raise NotImplementedError("List communities not allowed")

    async def search(self, query: str) -> List[Community]:
        """Search communities relevant to query."""
        chunks = await self._vector_store.asimilar_search_with_scores(
            query, self._topk, self._score_threshold
        )
        return [Community(id=chunk.chunk_id, summary=chunk.content) for chunk in chunks]

    async def save(self, communities: List[Community]):
        """Save communities."""
        chunks = [
            Chunk(id=c.id, content=c.summary, metadata={"total": len(communities)})
            for c in communities
        ]
        await self._vector_store.aload_document_with_limit(
            chunks, self._max_chunks_once_load, self._max_threads
        )
        logger.info(f"Save {len(communities)} communities")

    async def truncate(self):
        """Truncate community metastore."""
        self._vector_store.truncate()

    def drop(self):
        """Drop community metastore."""
        if self._vector_store.vector_name_exists():
            self._vector_store.delete_vector_name(self._vector_space)
