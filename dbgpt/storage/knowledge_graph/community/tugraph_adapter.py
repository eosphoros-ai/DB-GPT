"""TuGraph Community Store Adapter."""
import json
import logging
from typing import List

from dbgpt.storage.graph_store.graph import MemoryGraph
from dbgpt.storage.knowledge_graph.community.base import (
    Community,
    CommunityStoreAdapter,
)

logger = logging.getLogger(__name__)


class TuGraphCommunityStoreAdapter(CommunityStoreAdapter):
    """TuGraph Community Store Adapter."""

    MAX_HIERARCHY_LEVEL = 3

    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery with leiden."""
        mg = self._graph_store.query(
            "CALL db.plugin.callPlugin"
            "('CPP','leiden','{\"leiden_val\":\"_community_id\"}',60.00,false)"
        )
        result = mg.get_vertex("json_node").get_prop("description")
        community_ids = json.loads(result)["community_id_list"]
        logger.info(f"Discovered {len(community_ids)} communities.")
        return community_ids

    async def get_community(self, community_id: str) -> Community:
        """Get community."""
        query = (
            f"MATCH (n:{self._graph_store.get_vertex_type()})"
            f"WHERE n._community_id = '{community_id}' RETURN n"
        )
        edge_query = (
            f"MATCH (n:{self._graph_store.get_vertex_type()})-"
            f"[r:{self._graph_store.get_edge_type()}]-"
            f"(m:{self._graph_store.get_vertex_type()})"
            f"WHERE n._community_id = '{community_id}' RETURN n,r,m"
        )

        all_vertex_graph = self._graph_store.aquery(query)
        all_edge_graph = self._graph_store.aquery(edge_query)
        all_graph = MemoryGraph()
        for vertex in all_vertex_graph.vertices():
            all_graph.upsert_vertex(vertex)
        for edge in all_edge_graph.edges():
            all_graph.append_edge(edge)

        return Community(id=community_id, data=all_graph)
