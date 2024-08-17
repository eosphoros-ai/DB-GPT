"""Define the CommunityStore class"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Generator, List

from openai import OpenAI

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.community.community_metastore import \
    CommunityMetastore
from dbgpt.storage.graph_store.graph import Vertex, Graph

logger = logging.getLogger(__name__)

client = OpenAI(api_key="")

@dataclass
class Community:
    id: str
    data: Graph = None
    summary: str = None


class CommunityStore:

    def __init__(
        self,
        graph_store: GraphStoreBase,
        meta_store: CommunityMetastore
    ):
        """Initialize the CommunityStore"""
        self._graph_store = graph_store
        self._meta_store = meta_store
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._max_hierarchy_level = 3

    async def build_communities(self):
        # discover communities
        graph_name = self._graph_store.get_config().name
        query = f"CALL {graph_name}.leiden()"
        communities_metadata = self._graph_store.stream_query(query)
        logger.info(f"Discover {len(communities_metadata)} communities.")

        # summarize communities
        communities = await self._retrieve_communities(communities_metadata)
        await self._summarize_communities(communities)

    async def _retrieve_communities(
        self, communities_metadata: Generator[Graph, None, None]
    ) -> List[Community]:
        """Collect detailed information for each node based on their community.

        # community_hierarchical_clusters structure: Generator[Graph, None, None]
        Each Graph contains:
            vertices: A set of Vertex objects, each representing a node in the graph.
            edges: A set of Edge objects, each representing an edge in the graph.
            Vertex objects may include the following attributes:

            id: A unique identifier for the node
            properties: A dictionary containing other properties of the node, e.g., {"community_id": "cluster1"}
            Edge objects may include the following attributes:

            src_id: The ID of the source node of the edge
            dst_id: The ID of the destination node of the edge
            label: The label or type of the edge
            properties: A dictionary containing other properties of the edge, e.g., {"description": "some relationship"}

        # community_info example
        {
            "cluster1": [
                "node1 -> node2 -> relationship_type -> relationship description",
                "node1 -> node3 -> another_relationship -> another description",
            ],
            "cluster2": [
                "node4 -> node5 -> some_relationship -> some description",
            ],
        }

        """

        community_info: List[Community] = []
        tasks = []

        for memory_graph in communities_metadata:
            for vertex in memory_graph.vertices:
                task = asyncio.create_task(
                    self._process_vertex(memory_graph, vertex, community_info)
                )
                tasks.append(task)

        await asyncio.gather(*tasks)

        if self._enable_persistence and self._orm:
            await asyncio.get_event_loop().run_in_executor(
                self._executor, self._orm.save_community_info, community_info
            )

        return community_info

    async def _process_vertex(
        self,
        memory_graph: Graph,
        vertex: Vertex,
        communities: List[Community],
    ):
        cluster_id = vertex.properties.get("community_id", "unknown")
        if cluster_id not in communities:
            communities[cluster_id] = []

        for edge in memory_graph.edges:
            if edge.src_id == vertex.id:
                neighbor_vertex = memory_graph.get_vertex(edge.dst_id)
                if neighbor_vertex:
                    detail = f"{vertex.id} -> {neighbor_vertex.id} -> {edge.label} -> {edge.properties.get('description', 'No description')}"
                    communities[cluster_id].append(detail)

    async def _summarize_communities(self, communities: List[Community]):
        """Generate and store summaries for each community."""
        tasks = []
        for community in communities:
            task = asyncio.create_task(self._summarize_community(community))
            tasks.append(task)
        await asyncio.gather(*tasks)

    async def _summarize_community(self, community: Community):
        summary = await self._generate_community_summary(community.data)
        community.summary = summary
        self._meta_store.save([community])

    async def search_communities(self, query: str) -> List[Community]:
        return await self._meta_store.search(query)

    async def _generate_community_summary(self, graph: Graph):
        """Generate summary for a given text using an LLM."""
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        """Task: Summarize Knowledge Graph Relationships
                        
                        You are given relationships from a knowledge graph in the format:
                        entity1 -> entity2 -> relation -> relationship_description.
                        
                        Goal: Create a concise summary that includes the entities' names and synthesizes the relationship descriptions, highlighting the most critical and relevant details. Ensure coherence and emphasize key aspects of each relationship.
                        """
                    ),
                },
                {"role": "user", "content": graph},
            ],
        )
        return response.choices[0].message.content
