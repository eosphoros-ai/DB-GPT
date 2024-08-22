"""Define the CommunityStore class"""

import json
import logging
from typing import List, Set

from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.community import Community
from dbgpt.storage.graph_store.graph import Graph
from dbgpt.storage.knowledge_graph.community.community_metastore import \
    BuiltinCommunityMetastore
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)


class CommunityStore:
    MAX_HIERARCHY_LEVEL = 3

    def __init__(
        self,
        graph_store: GraphStoreBase,
        community_summarizer: CommunitySummarizer,
        vector_store: VectorStoreBase
    ):
        """Initialize the CommunityStore"""
        self._graph_store = graph_store
        self._community_summarizer = community_summarizer
        self._meta_store = BuiltinCommunityMetastore(vector_store)

    async def build_communities(self):
        """Discover, retrieve, summarize and save communities."""
        community_ids = await self.__discover_communities()

        communities = []
        for community_id in community_ids:
            community = await self.__retrieve_community(community_id)
            community.summary = await (
                self.__summarize_community(community.data)
            )
            communities.append(community)

        await self._meta_store.save(communities)

    async def __discover_communities(self) -> Set[str]:
        """Discover unique community IDs."""
        # graph_name = self._graph_store.get_config().name
        mg = self._graph_store.query(
            "CALL db.plugin.callPlugin"
            "('CPP','leiden','{\"leiden_val\":\"_community_id\"}',60.00,false)"
        )
        result = mg.get_vertex("json_node").get_prop('description')
        community_ids = json.loads(result)["community_id_list"]
        logger.info(f"Discovered {len(community_ids)} communities.")
        return community_ids

    async def __retrieve_community(
        self, community_id: str
    ) -> Community:
        """Retrieve community data for community id."""
        gql = (
            f"MATCH (n:{self._graph_store._node_label})-"
            f"[r:{self._graph_store._edge_label}]-"
            f"(m:{self._graph_store._node_label}) "
            f"WHERE n._community_id = '{community_id}' RETURN n,r,m"
        )
        return Community(id=community_id, data=self._graph_store.aquery(gql))

    async def __summarize_community(self, graph: Graph):
        """Generate summary for a given graph using an LLM."""
        # todo remove (chunk and doc) vertex 
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
        self._graph_store.drop()
        self._meta_store.drop()
