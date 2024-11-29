"""Define the CommunityStore class."""

import asyncio
import logging
from typing import List, Optional

from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.storage.knowledge_graph.community.base import Community, GraphStoreAdapter
from dbgpt.storage.knowledge_graph.community.community_metastore import (
    BuiltinCommunityMetastore,
)
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)


class CommunityStore:
    """CommunityStore Class."""

    def __init__(
        self,
        graph_store_adapter: GraphStoreAdapter,
        community_summarizer: CommunitySummarizer,
        vector_store: VectorStoreBase,
    ):
        """Initialize the CommunityStore class."""
        self._graph_store_adapter = graph_store_adapter
        self._community_summarizer = community_summarizer
        self._meta_store = BuiltinCommunityMetastore(vector_store)

    async def build_communities(self, batch_size: int = 1):
        """Discover communities."""
        community_ids = await self._graph_store_adapter.discover_communities()

        # summarize communities
        communities = []
        n_communities = len(community_ids)

        for i in range(0, n_communities, batch_size):
            batch_ids = community_ids[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self._summary_community(cid) for cid in batch_ids]
            )
            # filter out None returns
            communities.extend([c for c in batch_results if c is not None])

        # truncate then save new summaries
        await self._meta_store.truncate()
        await self._meta_store.save(communities)

    async def _summary_community(self, community_id: str) -> Optional[Community]:
        """Summarize single community."""
        community = await self._graph_store_adapter.get_community(community_id)
        if community is None or community.data is None:
            logger.warning(f"Community {community_id} is empty")
            return None

        graph = community.data.format()
        community.summary = await self._community_summarizer.summarize(graph=graph)
        logger.info(f"Summarize community {community_id}: {community.summary[:50]}...")
        return community

    async def search_communities(self, query: str) -> List[Community]:
        """Search communities."""
        return await self._meta_store.search(query)

    def truncate(self):
        """Truncate community store."""
        logger.info("Truncate community metastore")
        self._meta_store.truncate()

        logger.info("Truncate community summarizer")
        self._community_summarizer.truncate()

        logger.info("Truncate graph")
        self._graph_store_adapter.truncate()

    def drop(self):
        """Drop community store."""
        logger.info("Remove community metastore")
        self._meta_store.drop()

        logger.info("Remove community summarizer")
        self._community_summarizer.drop()

        logger.info("Remove graph")
        self._graph_store_adapter.drop()
