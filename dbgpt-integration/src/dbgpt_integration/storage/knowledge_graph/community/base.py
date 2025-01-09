"""Define Classes about Community."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Iterator, List, Literal, Optional, Union

from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)
from dbgpt.storage.knowledge_graph.base import ParagraphChunk

logger = logging.getLogger(__name__)


@dataclass
class Community:
    """Community class."""

    id: str
    data: Optional[Graph] = None
    summary: Optional[str] = None


@dataclass
class CommunityTree:
    """Represents a community tree."""


class GraphStoreAdapter(ABC):
    """Community Store Adapter."""

    def __init__(self, graph_store: GraphStoreBase):
        """Initialize Community Store Adapter."""
        self._graph_store = graph_store

    @property
    def graph_store(self) -> GraphStoreBase:
        """Get graph store."""
        return self._graph_store

    @abstractmethod
    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery."""

    @abstractmethod
    async def get_community(self, community_id: str) -> Community:
        """Get community."""

    @abstractmethod
    def get_graph_config(self):
        """Get config."""

    @abstractmethod
    def get_vertex_type(self) -> str:
        """Get vertex type."""

    @abstractmethod
    def get_edge_type(self) -> str:
        """Get edge type."""

    @abstractmethod
    def get_triplets(self, sub: str) -> List[tuple[str, str]]:
        """Get triplets."""

    @abstractmethod
    def get_document_vertex(self, doc_name: str) -> Vertex:
        """Get document vertex."""

    @abstractmethod
    def get_schema(self, refresh: bool = False) -> str:
        """Get schema."""

    @abstractmethod
    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Get full graph."""

    @abstractmethod
    def upsert_entities(self, entities: Iterator[Vertex]) -> None:
        """Upsert entity."""

    @abstractmethod
    def upsert_edge(
        self, edges: Iterator[Edge], edge_type: str, src_type: str, dst_type: str
    ):
        """Upsert edge."""

    @abstractmethod
    def upsert_chunks(
        self, chunks: Union[Iterator[Vertex], Iterator[ParagraphChunk]]
    ) -> None:
        """Upsert chunk."""

    @abstractmethod
    def upsert_documents(
        self, documents: Union[Iterator[Vertex], Iterator[ParagraphChunk]]
    ) -> None:
        """Upsert documents."""

    @abstractmethod
    def insert_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Insert triplet."""

    @abstractmethod
    def upsert_graph(self, graph: Graph) -> None:
        """Insert graph."""

    @abstractmethod
    def upsert_doc_include_chunk(
        self,
        chunk: ParagraphChunk,
    ) -> None:
        """Convert chunk to document include chunk."""

    @abstractmethod
    def upsert_chunk_include_chunk(
        self,
        chunk: ParagraphChunk,
    ) -> None:
        """Convert chunk to chunk include chunk."""

    @abstractmethod
    def upsert_chunk_next_chunk(
        self,
        chunk: ParagraphChunk,
        next_chunk: ParagraphChunk,
    ):
        """Uperst the vertices and the edge in chunk_next_chunk."""

    @abstractmethod
    def upsert_chunk_include_entity(
        self, chunk: ParagraphChunk, entity: Vertex
    ) -> None:
        """Convert chunk to chunk include entity."""

    @abstractmethod
    def delete_document(self, chunk_id: str) -> None:
        """Delete document in graph store."""

    @abstractmethod
    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""

    @abstractmethod
    def drop(self) -> None:
        """Drop graph."""

    @abstractmethod
    def create_graph(self, graph_name: str) -> None:
        """Create graph."""

    @abstractmethod
    def create_graph_label(
        self,
        graph_elem_type: GraphElemType,
        graph_properties: List[Dict[str, Union[str, bool]]],
    ) -> None:
        """Create a graph label.

        The graph label is used to identify and distinguish different types of nodes
        (vertices) and edges in the graph.
        """

    @abstractmethod
    def truncate(self) -> None:
        """Truncate graph."""

    @abstractmethod
    def check_label(self, graph_elem_type: GraphElemType) -> bool:
        """Check if the label exists in the graph."""

    @abstractmethod
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

    @abstractmethod
    def query(self, query: str, **kwargs) -> MemoryGraph:
        """Execute a query on graph."""

    @abstractmethod
    async def stream_query(self, query: str, **kwargs) -> AsyncGenerator[Graph, None]:
        """Execute a stream query."""


class CommunityMetastore(ABC):
    """Community metastore class."""

    @abstractmethod
    def get(self, community_id: str) -> Community:
        """Get community."""

    @abstractmethod
    def list(self) -> List[Community]:
        """Get all communities."""

    @abstractmethod
    async def search(self, query: str) -> List[Community]:
        """Search communities relevant to query."""

    @abstractmethod
    async def save(self, communities: List[Community]):
        """Save communities."""

    @abstractmethod
    async def truncate(self):
        """Truncate all communities."""

    @abstractmethod
    def drop(self):
        """Drop community metastore."""
