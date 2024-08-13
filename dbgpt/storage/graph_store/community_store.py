"""Define the CommunityStore class"""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Generator, List

from openai import OpenAI

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import MemoryGraph, Vertex

client = OpenAI(api_key="")


class SQLiteORM:
    def __init__(self, db_path: str = "communities.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._init_db()

    def _init_db(self):
        """Initialize the SQL database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS communities (
                    cluster_id TEXT PRIMARY KEY,
                    details TEXT
                )
                """
            )

    def _get_connection(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
        return self.conn, self.cursor

    def save_community_info(self, community_info: Dict[str, List[str]]):
        """Save community info to the SQL database."""
        conn, cursor = self._get_connection()
        with conn:
            cursor.executemany(
                "INSERT OR REPLACE INTO communities (cluster_id, details) VALUES (?, ?)",
                [(k, " ".join(v)) for k, v in community_info.items()],
            )

    def update_community_summary(self, community_id: str, summary: str):
        """Update community summary in the SQL database."""

        conn, cursor = self._get_connection()
        with conn:
            cursor.execute(
                "UPDATE communities SET details=? WHERE cluster_id=?",
                (summary, community_id),
            )

    def fetch_all_communities(self) -> Dict[str, str]:
        """Fetch all communities from SQL database."""

        conn, cursor = self._get_connection()
        cursor.execute("SELECT cluster_id, details FROM communities")
        return dict(cursor.fetchall())


class CommunityStore:
    def __init__(self, graph_store: GraphStoreBase, enable_persistence: bool = True):
        # Initialize with a graph store and maximum hierarchical level for Leiden algorithm
        self._graph_store = graph_store
        self._max_hierarchical_level = 3
        self._community_summary = {}
        self._enable_persistence = enable_persistence
        self._orm = SQLiteORM() if enable_persistence else None
        self._executor = ThreadPoolExecutor(max_workers=10)

    async def build_communities(self):
        # Build hierarchical communities using the Leiden algorithm
        LEIDEN_QUERY = ""  # TODO: create leiden query in TuGraph
        community_hierarchical_clusters = self._graph_store.stream_query(LEIDEN_QUERY)
        community_info = await self._retrieve_community_info(
            community_hierarchical_clusters
        )
        await self._summarize_communities(community_info)

    async def _retrieve_community_info(
        self, clusters: Generator[MemoryGraph, None, None]
    ) -> Dict[str, List[str]]:
        """Collect detailed information for each node based on their community.

        # community_hierarchical_clusters structure: Generator[MemoryGraph, None, None]
        Each MemoryGraph contains:
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

        community_info: Dict[str, List[str]] = {}
        tasks = []

        for memory_graph in clusters:
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
        memory_graph: MemoryGraph,
        vertex: Vertex,
        community_info: Dict[str, List[str]],
    ):
        cluster_id = vertex.properties.get("community_id", "unknown")
        if cluster_id not in community_info:
            community_info[cluster_id] = []

        for edge in memory_graph.edges:
            if edge.src_id == vertex.id:
                neighbor_vertex = memory_graph.get_vertex(edge.dst_id)
                if neighbor_vertex:
                    detail = f"{vertex.id} -> {neighbor_vertex.id} -> {edge.label} -> {edge.properties.get('description', 'No description')}"
                    community_info[cluster_id].append(detail)

    async def _summarize_communities(self, community_info: Dict[str, List[str]]):
        """Generate and store summaries for each community."""
        tasks = []
        for community_id, details in community_info.items():
            task = asyncio.create_task(self._summarize_community(community_id, details))
            tasks.append(task)
        await asyncio.gather(*tasks)

    async def _summarize_community(self, community_id: str, details: List[str]):
        details_text = f"{' '.join(details)}."
        summary = await self._generate_community_summary(details_text)
        self._community_summary[community_id] = summary

        if self._enable_persistence and self._orm:
            await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._orm.update_community_summary,
                community_id,
                summary,
            )

    async def summarize_communities(self) -> Dict[str, str]:
        if self._enable_persistence and self._orm:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor, self._orm.fetch_all_communities
            )
        else:
            return self._community_summary

    async def _generate_community_summary(self, text):
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
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content
