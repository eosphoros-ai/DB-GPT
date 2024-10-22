"""TuGraph Community Store Adapter."""

import json
import logging
from typing import AsyncGenerator, Dict, Iterator, List, Literal, Optional, Tuple, Union

from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)
from dbgpt.storage.graph_store.memgraph_store import (
    MemoryGraphStore,
    MemoryGraphStoreConfig,
)
from dbgpt.storage.knowledge_graph.base import ParagraphChunk
from dbgpt.storage.knowledge_graph.community.base import Community, GraphStoreAdapter

logger = logging.getLogger(__name__)


class MemGraphStoreAdapter(GraphStoreAdapter):
    """MemGraph Community Store Adapter."""

    MAX_HIERARCHY_LEVEL = 3

    def __init__(self, enable_summary: bool = False):
        """Initialize MemGraph Community Store Adapter."""
        self._graph_store = MemoryGraphStore(MemoryGraphStoreConfig())
        self._enable_summary = enable_summary

        super().__init__(self._graph_store)

        # Create the graph
        self.create_graph(self._graph_store.get_config().name)

    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery with leiden."""
        []

    async def get_community(self, community_id: str) -> Community:
        """Get community."""
        raise NotImplementedError("Memory graph store does not have community")

    def get_graph_config(self):
        """Get the graph store config."""
        return self._graph_store.get_config()

    def get_vertex_type(self) -> str:
        """Get the vertex type."""
        # raise NotImplementedError("Memory graph store does not have vertex type")
        return ""

    def get_edge_type(self) -> str:
        """Get the edge type."""
        # raise NotImplementedError("Memory graph store does not have edge type")
        return ""

    def get_triplets(self, subj: str) -> List[Tuple[str, str]]:
        """Get triplets."""
        subgraph = self.explore([subj], direct=Direction.OUT, depth=1)
        return [(e.name, e.tid) for e in subgraph.edges()]

    def get_document_vertex(self, doc_name: str) -> Vertex:
        """Get the document vertex in the graph."""
        raise NotImplementedError("Memory graph store does not have document vertex")

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        return json.dumps(self._graph_store._graph.schema())

    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Get full graph."""
        if not limit:
            return self._graph_store._graph

        subgraph = MemoryGraph()
        for count, edge in enumerate(self._graph_store._graph.edges()):
            if count >= limit:
                break
            subgraph.upsert_vertex(self._graph_store._graph.get_vertex(edge.sid))
            subgraph.upsert_vertex(self._graph_store._graph.get_vertex(edge.tid))
            subgraph.append_edge(edge)
            count += 1
        return subgraph

    def upsert_entities(self, entities: Iterator[Vertex]) -> None:
        """Upsert entities."""
        pass

    def upsert_edge(
        self, edges: Iterator[Edge], edge_type: str, src_type: str, dst_type: str
    ) -> None:
        """Upsert edges."""
        pass

    def upsert_chunks(
        self, chunks: Union[Iterator[Vertex], Iterator[ParagraphChunk]]
    ) -> None:
        """Upsert chunks."""
        pass

    def upsert_documents(
        self, documents: Union[Iterator[Vertex], Iterator[ParagraphChunk]]
    ) -> None:
        """Upsert documents."""
        pass

    def upsert_relations(self, relations: Iterator[Edge]) -> None:
        """Upsert relations."""
        pass

    def upsert_doc_include_chunk(
        self,
        chunk: ParagraphChunk,
    ) -> None:
        """Convert chunk to document include chunk."""
        pass

    def upsert_chunk_include_chunk(
        self,
        chunk: ParagraphChunk,
    ) -> None:
        """Convert chunk to chunk include chunk."""
        pass

    def upsert_chunk_next_chunk(
        self, chunk: ParagraphChunk, next_chunk: ParagraphChunk
    ):
        """Uperst the vertices and the edge in chunk_next_chunk."""
        pass

    def upsert_chunk_include_entity(
        self, chunk: ParagraphChunk, entity: Vertex
    ) -> None:
        """Convert chunk to chunk include entity."""
        pass

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        self._graph_store._graph.append_edge(Edge(subj, obj, rel))

    def upsert_graph(self, graph: Graph) -> None:
        """Add graph to the graph store.

        Args:
            graph (Graph): The graph to be added.
        """
        for vertex in graph.vertices():
            self._graph_store._graph.upsert_vertex(vertex)

        for edge in graph.edges():
            self._graph_store._graph.append_edge(edge)

    def delete_document(self, chunk_ids: str) -> None:
        """Delete document in the graph."""
        pass

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        self._graph_store._graph.del_edges(sub, obj, rel)

    def drop(self):
        """Delete Graph."""
        self._graph_store._graph = None

    def create_graph(self, graph_name: str):
        """Create a graph."""
        pass

    def create_graph_label(
        self,
        graph_elem_type: GraphElemType,
        graph_properties: List[Dict[str, Union[str, bool]]],
    ) -> None:
        """Create a graph label.

        The graph label is used to identify and distinguish different types of nodes
        (vertices) and edges in the graph.
        """
        pass

    def truncate(self):
        """Truncate Graph."""
        self._graph_store._graph.truncate()

    def check_label(self, graph_elem_type: GraphElemType) -> bool:
        """Check if the label exists in the graph.

        Args:
            graph_elem_type (GraphElemType): The type of the graph element.

        Returns:
            True if the label exists in the specified graph element type, otherwise
            False.
        """
        pass

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
        search_scope: Optional[
            Literal["knowledge_graph", "document_graph"]
        ] = "knowledge_graph",
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        return self._graph_store._graph.search(subs, direct, depth, fan, limit)

    def query(self, query: str, **kwargs) -> MemoryGraph:
        """Execute a query on graph."""
        pass

    async def stream_query(self, query: str, **kwargs) -> AsyncGenerator[Graph, None]:
        """Execute a stream query."""
        pass
