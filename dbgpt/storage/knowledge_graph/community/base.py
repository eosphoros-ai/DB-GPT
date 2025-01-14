"""Define Classes about Community."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Iterator, List, Optional, Union

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
    def explore_trigraph(
        self,
        subs: Union[List[str], List[List[float]]],
        topk: Optional[int] = None,
        score_threshold: Optional[float] = None,
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth.

        Args:
            subs (Union[List[str], List[List[float]]): The list of the subjects
                (keywords or embedding vectors).
            topk (Optional[int]): The number of the top similar entities.
            score_threshold (Optional[float]): The threshold of the similarity score.
            direct (Direction): The direction of the graph that will be explored.
            depth (int): The depth of the graph that will be explored.
            fan (Optional[int]): Not used.
            limit (Optional[int]): The limit number of the queried entities.

        Returns:
            MemoryGraph: The triplet graph that includes the entities and the relations.
        """

    @abstractmethod
    def explore_docgraph_with_entities(
        self,
        subs: List[str],
        topk: Optional[int] = None,
        score_threshold: Optional[float] = None,
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth.

        Args:
            subs (List[str]): The list of the entities.
            topk (Optional[int]): The number of the top similar chunks.
            score_threshold (Optional[float]): The threshold of the similarity score.
            direct (Direction): The direction of the graph that will be explored.
            depth (int): The depth of the graph that will be explored.
            fan (Optional[int]): Not used.
            limit (Optional[int]): The limit number of the queried chunks.

        Returns:
            MemoryGraph: The document graph that includes the leaf chunks that connect
                to the entities, the chains from documents to the leaf chunks, and the
                chain from documents to chunks.
        """

    @abstractmethod
    def explore_docgraph_without_entities(
        self,
        subs: Union[List[str], List[List[float]]],
        topk: Optional[int] = None,
        score_threshold: Optional[float] = None,
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth.

        Args:
            subs (Union[List[str], List[List[float]]): The list of the subjects
                (keywords or embedding vectors).
            topk (Optional[int]): The number of the top similar chunks.
            score_threshold (Optional[float]): The threshold of the similarity score.
            direct (Direction): The direction of the graph that will be explored.
            depth (int): The depth of the graph that will be explored.
            fan (Optional[int]): Not used.
            limit (Optional[int]): The limit number of the queried chunks.

        Returns:
            MemoryGraph: The document graph that includes the chains from documents
                to chunks that contain the subs (keywords) or similar chunks
                (embedding vectors).
        """

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


class GraphSyntaxValidator(ABC):
    """Community Syntax Validator."""

    @abstractmethod
    def validate(self, query: str) -> bool:
        """Validate query syntax."""
