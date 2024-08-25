"""TuGraph Community Store Adapter."""
import json
import logging
from typing import List

from dbgpt.storage.graph_store.community import Community
from dbgpt.storage.knowledge_graph.community.base import CommunityStoreAdapter

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
            f"MATCH (n:{self._graph_store.vertex_type})-"
            f"[r:{self._graph_store.edge_type}]-"
            f"(m:{self._graph_store.vertex_type}) "
            f"WHERE n._community_id = '{community_id}' RETURN n,r,m"
        )
        return Community(id=community_id, data=self._graph_store.aquery(query))
