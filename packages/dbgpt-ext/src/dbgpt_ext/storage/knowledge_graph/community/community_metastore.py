"""Builtin Community metastore."""

import logging
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt_ext.storage.knowledge_graph.community.base import (
    Community,
    CommunityMetastore,
)

logger = logging.getLogger(__name__)


class BuiltinCommunityMetastore(CommunityMetastore):
    """Builtin Community metastore."""

    def __init__(
        self,
        vector_store: VectorStoreBase,
        rdb_store: Optional[RDBMSConnector] = None,
        index_name: Optional[str] = None,
        max_chunks_once_load: Optional[int] = 10,
        max_threads: Optional[int] = 1,
        top_k: Optional[int] = 5,
        score_threshold: Optional[float] = 0.7,
    ):
        """Initialize Community metastore."""
        self._vector_store = vector_store
        self._rdb_store = rdb_store

        self._vector_space = index_name
        self._max_chunks_once_load = max_chunks_once_load
        self._max_threads = max_threads
        self._topk = top_k
        self._score_threshold = score_threshold

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
