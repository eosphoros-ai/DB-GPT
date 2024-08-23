"""Define the CommunityStore class"""

import logging
from typing import List

from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.storage.graph_store.community import Community
from dbgpt.storage.graph_store.graph import Graph
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
        """Discover, retrieve, summarize and save communities."""
        community_ids = await (
            self._community_store_adapter.discover_communities()
        )

        communities = []
        for community_id in community_ids:
            community = await (
                self._community_store_adapter.get_community(community_id)
            )
            community.summary = await (
                self.__summarize_community(community.data)
            )
            communities.append(community)

        await self._meta_store.save(communities)

    async def __summarize_community(self, graph: Graph):
        """Generate summary for a given graph using an LLM."""
        nodes = "\n".join(
            [
                f"- {v.vid}: {v.get_prop('description')}"
                for v in graph.vertices()
            ]
        )
        relationships = "\n".join(
            [
                f"- {e.sid} -> {e.tid}: {e.get_prop('label')} ({e.get_prop('description')})"
                for e in graph.edges()
            ]
        )

        return await self._community_summarizer.summarize(
            nodes=nodes, relationships=relationships
        )

    async def search_communities(self, query: str) -> List[Community]:
        return await self._meta_store.search(query)

    def drop(self):
        self._community_store_adapter.graph_store.drop()
        self._meta_store.drop()
