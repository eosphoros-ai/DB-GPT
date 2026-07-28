"""Code graph DB persistence service.

Provides save/load/search operations for code knowledge graphs
using relational database (SQLite/MySQL via SQLAlchemy).

Design:
  - Vertices and edges stored in dedicated tables with indexed columns
  - Props stored as JSON text for flexibility
  - Full-graph load for visualization/community detection
  - Targeted queries for search and neighbor lookup
  - Idempotent save (delete-then-insert)
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from dbgpt.storage.graph_store.graph import Edge, MemoryGraph, Vertex

from ..models.code_graph_db import (
    _VERTEX_PROPS_COLUMNS,
    CodeGraphEdgeDao,
    CodeGraphEdgeEntity,
    CodeGraphMetaDao,
    CodeGraphMetaEntity,
    CodeGraphVertexDao,
    CodeGraphVertexEntity,
)

logger = logging.getLogger(__name__)


class CodeGraphStore:
    """Code graph persistence layer backed by relational DB.

    Usage::

        store = CodeGraphStore()
        store.save_graph("knowledge_id", graph, build_source="chunks")
        graph = store.load_graph("knowledge_id")
        vertices = store.search_vertices("knowledge_id", name_prefix="Payment")
    """

    # Props that are extracted to dedicated vertex columns
    _VERTEX_PROP_COLUMNS = _VERTEX_PROPS_COLUMNS

    # Edge props that are extracted to dedicated edge columns
    _EDGE_PROP_COLUMNS = {"edge_type", "confidence", "source_file", "source_location"}

    def save_graph(
        self,
        knowledge_id: str,
        graph: MemoryGraph,
        build_source: str = "",
        repo_url: str = "",
        branch: str = "",
        community_count: int = 0,
    ) -> Dict:
        """Save a MemoryGraph to the database.

        Idempotent: deletes existing data for the knowledge_id first,
        then bulk-inserts all vertices and edges.

        Args:
            knowledge_id: Knowledge space ID.
            graph: The MemoryGraph to persist.
            build_source: How the graph was built ("chunks", "repo", "sync").
            repo_url: Git repository URL (if applicable).
            branch: Git branch (if applicable).
            community_count: Number of communities detected.

        Returns:
            Dict with save result (vertex_count, edge_count, etc.)
        """
        vertex_count = graph.vertex_count
        edge_count = graph.edge_count

        # 1. Delete old data (idempotent)
        self._delete_graph_data(knowledge_id)

        # 2. Convert vertices to row dicts
        vertex_rows = self._vertices_to_rows(knowledge_id, graph)

        # 3. Convert edges to row dicts
        edge_rows = self._edges_to_rows(knowledge_id, graph)

        # 4. Bulk insert vertices
        vertex_dao = CodeGraphVertexDao()
        inserted_vertices = vertex_dao.batch_insert(knowledge_id, vertex_rows)
        logger.info(
            f"Saved {inserted_vertices} vertices for knowledge_id={knowledge_id}"
        )

        # 5. Bulk insert edges
        edge_dao = CodeGraphEdgeDao()
        inserted_edges = edge_dao.batch_insert(knowledge_id, edge_rows)
        logger.info(f"Saved {inserted_edges} edges for knowledge_id={knowledge_id}")

        # 6. Upsert meta
        meta = CodeGraphMetaEntity(
            knowledge_id=knowledge_id,
            vertex_count=vertex_count,
            edge_count=edge_count,
            community_count=community_count,
            build_source=build_source,
            repo_url=repo_url,
            branch=branch,
            build_status="completed",
            graph_version=1,
        )
        meta_dao = CodeGraphMetaDao()
        meta_dao.upsert(meta)

        return {
            "knowledge_id": knowledge_id,
            "vertex_count": inserted_vertices,
            "edge_count": inserted_edges,
            "community_count": community_count,
            "build_source": build_source,
        }

    def load_graph(self, knowledge_id: str) -> Optional[MemoryGraph]:
        """Load a MemoryGraph from the database.

        Args:
            knowledge_id: Knowledge space ID.

        Returns:
            MemoryGraph instance, or None if not found.
        """
        # 1. Load vertices
        vertex_dao = CodeGraphVertexDao()
        vertex_entities = vertex_dao.get_by_knowledge_id(knowledge_id)
        if not vertex_entities:
            logger.warning(f"No vertices found for knowledge_id={knowledge_id}")
            return None

        # 2. Load edges
        edge_dao = CodeGraphEdgeDao()
        edge_entities = edge_dao.get_by_knowledge_id(knowledge_id)

        # 3. Build MemoryGraph
        graph = MemoryGraph()

        # Add vertices
        vertex_map = {}
        for v in vertex_entities:
            vertex = self._entity_to_vertex(v)
            graph.upsert_vertex(vertex)
            vertex_map[v.vid] = vertex

        # Add edges
        for e in edge_entities:
            sid_vertex = vertex_map.get(e.sid)
            tid_vertex = vertex_map.get(e.tid)
            if sid_vertex and tid_vertex:
                edge = self._entity_to_edge(e, sid_vertex, tid_vertex)
                graph.append_edge(edge)
            else:
                logger.warning(
                    f"Skipping edge with missing vertex: sid={e.sid}, tid={e.tid}"
                )

        logger.info(
            f"Loaded graph for knowledge_id={knowledge_id}: "
            f"{len(vertex_entities)} vertices, {len(edge_entities)} edges"
        )
        return graph

    def search_vertices(
        self,
        knowledge_id: str,
        name_prefix: Optional[str] = None,
        node_type: Optional[str] = None,
        source_file: Optional[str] = None,
        limit: int = 20,
    ) -> List[Vertex]:
        """Search vertices by various criteria.

        Args:
            knowledge_id: Knowledge space ID.
            name_prefix: Filter by name prefix.
            node_type: Filter by node type (e.g., "class", "function").
            source_file: Filter by source file path.
            limit: Maximum results to return.

        Returns:
            List of Vertex objects.
        """
        vertex_dao = CodeGraphVertexDao()

        # Priority: name_prefix > source_file > all
        if name_prefix:
            entities = vertex_dao.search_by_name(
                knowledge_id, name_prefix, node_type, limit
            )
        elif source_file:
            entities = vertex_dao.get_by_source_file(knowledge_id, source_file)
        else:
            entities = vertex_dao.get_by_knowledge_id(knowledge_id)[:limit]

        return [self._entity_to_vertex(e) for e in entities]

    def get_neighbors(
        self,
        knowledge_id: str,
        vid: str,
        edge_type: Optional[str] = None,
        direction: str = "both",
    ) -> Tuple[List[Vertex], List[Edge]]:
        """Get neighboring vertices and edges for a given vertex.

        Args:
            knowledge_id: Knowledge space ID.
            vid: Vertex ID to find neighbors for.
            edge_type: Filter by edge type.
            direction: "out" (edges from vid), "in" (edges to vid), or "both".

        Returns:
            Tuple of (neighbor_vertices, edges).
        """
        vertex_dao = CodeGraphVertexDao()
        edge_dao = CodeGraphEdgeDao()

        # Get the source vertex
        source_vertex = vertex_dao.get_by_vid(knowledge_id, vid)
        if not source_vertex:
            return [], []

        neighbor_vids = set()
        edges = []

        # Get outgoing edges
        if direction in ("out", "both"):
            out_edges = edge_dao.get_out_edges(knowledge_id, vid, edge_type)
            for e in out_edges:
                edges.append(self._entity_to_edge(e, None, None))
                neighbor_vids.add(e.tid)

        # Get incoming edges
        if direction in ("in", "both"):
            in_edges = edge_dao.get_in_edges(knowledge_id, vid, edge_type)
            for e in in_edges:
                edges.append(self._entity_to_edge(e, None, None))
                neighbor_vids.add(e.sid)

        # Load neighbor vertices
        neighbors = []
        for neighbor_vid in neighbor_vids:
            neighbor = vertex_dao.get_by_vid(knowledge_id, neighbor_vid)
            if neighbor:
                neighbors.append(self._entity_to_vertex(neighbor))

        return neighbors, edges

    def get_meta(self, knowledge_id: str) -> Optional[Dict]:
        """Get graph metadata for a knowledge space.

        Args:
            knowledge_id: Knowledge space ID.

        Returns:
            Dict with metadata, or None if not found.
        """
        meta_dao = CodeGraphMetaDao()
        meta = meta_dao.get_by_knowledge_id(knowledge_id)
        return meta.to_dict() if meta else None

    def delete_graph(self, knowledge_id: str) -> bool:
        """Delete all graph data for a knowledge space.

        Args:
            knowledge_id: Knowledge space ID.

        Returns:
            True if deleted, False if not found.
        """
        self._delete_graph_data(knowledge_id)
        return True

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _delete_graph_data(self, knowledge_id: str) -> None:
        """Delete all graph data for a knowledge space."""
        vertex_dao = CodeGraphVertexDao()
        edge_dao = CodeGraphEdgeDao()
        meta_dao = CodeGraphMetaDao()

        vertex_dao.delete_by_knowledge_id(knowledge_id)
        edge_dao.delete_by_knowledge_id(knowledge_id)
        meta_dao.delete_by_knowledge_id(knowledge_id)

    def _vertices_to_rows(self, knowledge_id: str, graph: MemoryGraph) -> List[Dict]:
        """Convert MemoryGraph vertices to DB row dicts.

        DB-GPT's RepoGraphBuilder stores props like:
          - type -> mapped to node_type column
          - file_path -> mapped to source_file column
          - language -> mapped to language column
          - start_line, end_line, url, path -> stored in props JSON
        """
        rows = []
        for vertex in graph.vertices():
            props = vertex.props or {}
            row = {
                "vid": vertex.vid,
                "name": vertex.name,
                # Map "type" prop to node_type column (DB-GPT uses "type")
                "node_type": props.get("type", props.get("node_type", "")),
                # Map "file_path"/"path" prop to source_file column
                "source_file": props.get(
                    "file_path", props.get("path", props.get("source_file", ""))
                ),
                "language": props.get("language", ""),
                "community": props.get("community", ""),
                # Store remaining props as JSON (excluding extracted columns)
                "props": json.dumps(
                    {
                        k: v
                        for k, v in props.items()
                        if k not in self._VERTEX_PROP_COLUMNS
                        and k not in ("type", "file_path", "path")
                    }
                ),
            }
            rows.append(row)
        return rows

    def _edges_to_rows(self, knowledge_id: str, graph: MemoryGraph) -> List[Dict]:
        """Convert MemoryGraph edges to DB row dicts.

        DB-GPT's RepoGraphBuilder stores edge props like:
          - type -> mapped to edge_type column
          - source_file, source_location -> dedicated columns
          - confidence -> default EXTRACTED
        """
        rows = []
        for edge in graph.edges():
            props = edge.props or {}
            row = {
                "sid": edge.sid,
                "tid": edge.tid,
                # Map "type" prop to edge_type column
                "edge_type": props.get("type", props.get("edge_type", "references")),
                "confidence": props.get("confidence", "EXTRACTED"),
                "source_file": props.get("source_file", ""),
                "source_location": props.get("source_location", ""),
                # Store remaining props as JSON
                "props": json.dumps(
                    {
                        k: v
                        for k, v in props.items()
                        if k not in self._EDGE_PROP_COLUMNS and k not in ("type",)
                    }
                ),
            }
            rows.append(row)
        return rows

    def _entity_to_vertex(self, entity: CodeGraphVertexEntity) -> Vertex:
        """Convert DB entity to Vertex.

        Reconstructs the props dict by merging dedicated columns back in.
        Uses "type" key (matching DB-GPT's RepoGraphBuilder convention)
        instead of "node_type" (derisk convention).
        """
        # Parse props JSON
        props = {}
        if entity.props:
            try:
                props = json.loads(entity.props)
            except json.JSONDecodeError:
                pass

        # Add dedicated columns back to props using DB-GPT convention
        props["type"] = entity.node_type
        props["file_path"] = entity.source_file
        props["language"] = entity.language
        if entity.community:
            props["community"] = entity.community

        return Vertex(
            vid=entity.vid,
            name=entity.name,
            **props,
        )

    def _entity_to_edge(
        self,
        entity: CodeGraphEdgeEntity,
        source_vertex: Optional[Vertex],
        target_vertex: Optional[Vertex],
    ) -> Edge:
        """Convert DB entity to Edge.

        Reconstructs the props dict by merging dedicated columns back in.
        Uses "type" key (matching DB-GPT's RepoGraphBuilder convention).
        """
        # Parse props JSON
        props = {}
        if entity.props:
            try:
                props = json.loads(entity.props)
            except json.JSONDecodeError:
                pass

        # Add dedicated columns back to props using DB-GPT convention
        props["type"] = entity.edge_type
        props["confidence"] = entity.confidence
        props["source_file"] = entity.source_file
        props["source_location"] = entity.source_location

        return Edge(
            sid=entity.sid,
            tid=entity.tid,
            name=entity.edge_type,
            **props,
        )
