"""Define the CommunityStore class"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Generator, List

from openai import OpenAI
from sqlalchemy import text

from dbgpt.datasource.rdbms.conn_sqlite import SQLiteConnector
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Vertex, Graph

client = OpenAI(api_key="")


class SQLiteORM:
    def __init__(self, db_path: str = "communities.db"):
        self.connector = SQLiteConnector.from_file_path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the SQL database."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS communities (
            cluster_id TEXT PRIMARY KEY,
            details TEXT
        )
        """
        self.connector._write(create_table_sql)

    def save_community_info(self, community_info: Dict[str, List[str]]):
        """Save community info to the SQL database."""
        insert_sql = """
        INSERT OR REPLACE INTO communities (cluster_id, details) VALUES (:cluster_id, :details)
        """
        params = [
            {"cluster_id": k, "details": " ".join(v)} for k, v in community_info.items()
        ]
        self.connector.session.execute(text(insert_sql), params)
        self.connector.session.commit()

    def update_community_summary(self, community_id: str, summary: str):
        """Update community summary in the SQL database."""
        update_sql = """
        UPDATE communities SET details = :details WHERE cluster_id = :cluster_id
        """
        params = {"details": summary, "cluster_id": community_id}
        self.connector.session.execute(text(update_sql), params)
        self.connector.session.commit()

    def fetch_all_communities(self) -> Dict[str, str]:
        """Fetch all communities from SQL database."""
        select_sql = "SELECT cluster_id, details FROM communities"
        result = self.connector.session.execute(text(select_sql))
        return dict(result.fetchall())

    def __del__(self):
        """Close the connection when the object is deleted."""
        if self.connector:
            self.connector.close()


class Community:
    id: str
    level: str
    data: Graph
    summary: str = None


class CommunityStore:
    def __init__(self, graph_store: GraphStoreBase, enable_persistence: bool = True):
        # Initialize with a graph store and maximum hierarchical level for Leiden algorithm
        self._graph_store = graph_store
        self._max_hierarchy_level = 3
        self._enable_persistence = enable_persistence
        self._orm = SQLiteORM() if enable_persistence else None
        self._executor = ThreadPoolExecutor(max_workers=10)

    async def build_communities(self):
        # discover communities
        graph_name = self._graph_store.get_config().name
        query = f"CALL {graph_name}.leiden({self._max_hierarchy_level})"
        communities_metadata = self._graph_store.stream_query(query)

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

        if self._enable_persistence and self._orm:
            await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._orm.update_community_summary,
                community.id,
                summary,
            )

    async def search_communities(self, query: str) -> List[Community]:
        # TODO: search communities relevant with query (by RDB / Vector / index)
        if self._enable_persistence and self._orm:
            return await asyncio.get_event_loop().run_in_executor(
                self._executor, self._orm.fetch_all_communities
            )
        else:
            # TODO: in-memory search cache can be used here
            return

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
