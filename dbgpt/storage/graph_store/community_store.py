"""Define the CommunityStore class"""

import logging
from typing import List

from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.storage.graph_store.community import Community
from dbgpt.storage.knowledge_graph.community.base import CommunityStoreAdapter
from dbgpt.storage.knowledge_graph.community.community_metastore import \
    BuiltinCommunityMetastore
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)


class CommunityStore:

    def __init__(
        self,
        community_store_adapter: CommunityStoreAdapter,
        community_summarizer: CommunitySummarizer,
        vector_store: VectorStoreBase
    ):
        """Initialize the CommunityStore"""
        self._community_store_adapter = community_store_adapter
        self._community_summarizer = community_summarizer
        self._meta_store = BuiltinCommunityMetastore(vector_store)

    async def build_communities(self):
        """discover communities."""
        community_ids = await (
            self._community_store_adapter.discover_communities()
        )

        # summarize communities
        communities = []
        for community_id in community_ids:
            community = await (
                self._community_store_adapter.get_community(community_id)
            )
            community.summary = await (
                # todo: use concise format
                self._community_summarizer.summarize(
                    graph=community.data.format()
                )
            )
            communities.append(community)
            logger.info(
                f"Summarize community {community_id}: "
                f"{community.summary[:50]}..."
            )

        # save summaries
        await self._meta_store.save(communities)

    async def search_communities(self, query: str) -> List[Community]:
        return await self._meta_store.search(query)

    def drop(self):
        logger.info(f"Remove graph")
        self._community_store_adapter.graph_store.drop()

        logger.info(f"Remove community metastore")
        self._meta_store.drop()
