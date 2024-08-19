"""Define the CommunityStore class"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Set

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Graph
from dbgpt.storage.knowledge_graph.community.community_metastore import (
    CommunityMetastore,
)

logger = logging.getLogger(__name__)


@dataclass
class Community:
    id: str
    data: Graph = None
    summary: str = None


@dataclass
class CommunityTree:
    """Represents a community tree."""


class CommunityStore:

    def __init__(
        self,
        graph_store: GraphStoreBase,
        meta_store: CommunityMetastore,
        llm_client: LLMClient,
        model_name: str,
    ):
        """Initialize the CommunityStore"""
        self._graph_store = graph_store
        self._meta_store = meta_store
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._max_hierarchy_level = 3
        self._llm_extractor = LLMExtractor(llm_client, model_name)

    async def build_communities(self):
        """Discover, retrieve, summarize and save communities."""
        communities_metadata = await self.discover_communities()
        communities = await self.retrieve_communities(communities_metadata)
        await self.summarize_communities(communities)
        await self.save_communities(communities)

    async def discover_communities(self) -> Set[str]:
        """Discover unique community IDs."""
        graph_name = self._graph_store.get_config().name
        community_ids = set(
            self._graph_store.stream_query(f"CALL {graph_name}.leiden()")
        )
        logger.info(f"Discovered {len(community_ids)} communities.")
        return community_ids

    async def retrieve_communities(self, community_ids: Set[str]) -> List[Community]:
        """Retrieve community data for each community ID."""

        async def process_community(community_id: str) -> Community:
            community = Community(id=community_id, data=Graph())
            nodes = self._graph_store.stream_query(
                f"MATCH (n:{self._graph_store._node_label}) WHERE n._community_id = '{community_id}' RETURN n"
            )

            for node in nodes:
                vertex = node.vertices[0]
                community.data.upsert_vertex(vertex)
                edges = self._graph_store.stream_query(
                    f"MATCH (n:{self._graph_store._node_label})-[r:{self._graph_store._edge_label}]->(m:{self._graph_store._node_label}) WHERE n.id = '{vertex.vid}' RETURN r, m"
                )
                for edge_result in edges:
                    edge, target_vertex = edge_result.edges[0], edge_result.vertices[0]
                    community.data.append_edge(edge)
                    community.data.upsert_vertex(target_vertex)

            return community

        return await asyncio.gather(*[process_community(cid) for cid in community_ids])

    async def summarize_communities(self, communities: List[Community]):
        """Generate summaries for each community."""
        for community in communities:
            community.summary = await self._generate_community_summary(community.data)

    async def save_communities(self, communities: List[Community]):
        """Save all communities to the meta store."""
        await asyncio.get_event_loop().run_in_executor(
            self._executor, self._meta_store.save, communities
        )

    async def search_communities(self, query: str) -> List[Community]:
        return await self._meta_store.search(query)

    async def _summarize_community(self, community: Community):
        summary = await self._generate_community_summary(community.data)
        community.summary = summary
        self._meta_store.save([community])

    async def _generate_community_summary(self, graph: Graph):
        """Generate summary for a given graph using an LLM."""
        prompt_template = """Task: Summarize Knowledge Graph Community

        You are given a community from a knowledge graph with the following information:
        1. Nodes (entities) with their descriptions
        2. Relationships between nodes with their descriptions

        Goal: Create a concise summary that:
        1. Identifies the main themes or topics of this community
        2. Highlights key entities and their roles
        3. Summarizes the most important relationships
        4. Provides an overall characterization of what this community represents

        Community Data:
        Nodes: {nodes}
        Relationships: {relationships}

        Summary:"""

        nodes = "\n".join(
            [f"- {v.vid}: {v.get_prop('description')}" for v in graph.vertices()]
        )
        relationships = "\n".join(
            [
                f"- {e.sid} -> {e.tid}: {e.get_prop('label')} ({e.get_prop('description')})"
                for e in graph.edges()
            ]
        )

        return await self._llm_extractor.extract(
            prompt_template.format(nodes=nodes, relationships=relationships)
        )
