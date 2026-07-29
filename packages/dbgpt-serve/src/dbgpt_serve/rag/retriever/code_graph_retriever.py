"""Code graph retriever — search code knowledge graphs for relevant context.

Three query modes:
  1. Entity search: "What does UserService do?" -> find class node, expand to methods
  2. Call chain search: "Who calls process_payment?" -> reverse BFS on CALLS edges
  3. Inheritance search: "What implements PaymentProvider?" -> traverse IMPLEMENTS edges

The retriever formats the subgraph as structured text context and returns
it as Chunk objects with metadata indicating the retrieval source.

Ported from derisk; adapted to DB-GPT's dbgpt.core / dbgpt.storage / dbgpt.rag
module paths.
"""

import logging
import re
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from dbgpt.core import Chunk
from dbgpt.rag.graph_extractor.schema import CodeEdgeType, CodeNodeType
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.storage.graph_store.graph import Direction, MemoryGraph, Vertex
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)

# Edge priority for BFS traversal (higher = traversed first)
_EDGE_PRIORITY = {
    CodeEdgeType.CONTAINS.value: 3,
    CodeEdgeType.CALLS.value: 2,
    CodeEdgeType.INHERITS.value: 2,
    CodeEdgeType.IMPLEMENTS.value: 2,
    CodeEdgeType.IMPORTS.value: 1,
    CodeEdgeType.REFERENCES.value: 1,
}

# Maximum characters per code block in formatted output
_MAX_CODE_BLOCK_CHARS = 1500

# Maximum BFS depth
_DEFAULT_BFS_DEPTH = 2

# Maximum nodes in a subgraph result
_MAX_SUBGRAPH_NODES = 50


class CodeGraphRetriever(BaseRetriever):
    """Retrieve code context from a knowledge graph.

    Searches the graph for nodes matching query keywords, then expands
    the subgraph via BFS to provide structural context (call chains,
    inheritance, containment).

    Usage::

        retriever = CodeGraphRetriever(graph=code_graph)
        chunks = retriever.retrieve("UserService")
        chunks = retriever.retrieve("who calls process_payment")
    """

    def __init__(
        self,
        graph: MemoryGraph,
        knowledge_id: str = "",
        top_k: int = 10,
        bfs_depth: int = _DEFAULT_BFS_DEPTH,
        max_subgraph_nodes: int = _MAX_SUBGRAPH_NODES,
    ):
        """Initialize the code graph retriever.

        Args:
            graph: The MemoryGraph containing the code knowledge graph.
            knowledge_id: The knowledge space ID (for metadata).
            top_k: Maximum number of result chunks.
            bfs_depth: BFS expansion depth from matched nodes.
            max_subgraph_nodes: Maximum nodes in a subgraph result.
        """
        self._graph = graph
        self._knowledge_id = knowledge_id
        self._top_k = int(top_k)
        self._bfs_depth = int(bfs_depth)
        self._max_subgraph_nodes = int(max_subgraph_nodes)

        # Build name -> vertex index for fast lookup
        self._name_index: Dict[str, List[Vertex]] = {}
        self._vid_index: Dict[str, Vertex] = {}
        self._build_index()

    def _build_index(self):
        """Build name and vid indexes from the graph."""
        for v in self._graph.vertices():
            # Index by vertex ID
            self._vid_index[v.vid] = v

            # Index by name (case-insensitive)
            name_lower = v.name.lower() if v.name else ""
            if name_lower:
                if name_lower not in self._name_index:
                    self._name_index[name_lower] = []
                self._name_index[name_lower].append(v)

            # Also index by the last part of vid (e.g. "paymentservice" from
            # "services_payment_paymentservice")
            vid_parts = v.vid.split("_")
            if len(vid_parts) > 1:
                last_part = vid_parts[-1].lower()
                if last_part not in self._name_index:
                    self._name_index[last_part] = []
                self._name_index[last_part].append(v)

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve code context from the graph.

        Args:
            query: Search query (e.g. "UserService", "who calls process_payment").
            filters: Not used for graph retrieval.

        Returns:
            List of Chunk objects with formatted graph context.
        """
        # Detect query mode
        mode = self._detect_query_mode(query)

        # Extract search terms from query
        terms = self._extract_search_terms(query)
        if not terms:
            return []

        # Find matching nodes
        matched_nodes = self._find_matching_nodes(terms)
        if not matched_nodes:
            return []

        # Expand subgraph based on query mode
        if mode == "call_chain":
            subgraph = self._expand_call_chain(matched_nodes, reverse=True)
        elif mode == "inheritance":
            subgraph = self._expand_inheritance(matched_nodes)
        else:
            subgraph = self._expand_bfs(matched_nodes)

        if subgraph.vertex_count == 0:
            return []

        # Format subgraph as text chunks
        return self._format_subgraph(subgraph, mode, query)

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Async version of _retrieve."""
        return self._retrieve(query, filters)

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve with score threshold (graph results always have score=1.0)."""
        chunks = self._retrieve(query, filters)
        return [c for c in chunks if c.metadata.get("score", 1.0) >= score_threshold]

    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Async retrieve with score threshold."""
        return self._retrieve_with_score(query, score_threshold, filters)

    # ------------------------------------------------------------------
    # Query mode detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_query_mode(query: str) -> str:
        """Detect the query mode from natural language patterns.

        Returns:
            "call_chain" for call chain queries,
            "inheritance" for inheritance queries,
            "entity" for entity search (default).
        """
        q = query.lower()

        # Call chain patterns
        call_patterns = [
            r"who calls",
            r"who invokes",
            r"callers of",
            r"what calls",
            r"what invokes",
            r"调用链",
            r"谁调用",
            r"调用者",
            r"call chain",
            r"call graph",
        ]
        for pattern in call_patterns:
            if re.search(pattern, q):
                return "call_chain"

        # Inheritance patterns
        inherit_patterns = [
            r"what implements",
            r"what extends",
            r"subclasses of",
            r"implementations of",
            r"inherits from",
            r"实现了",
            r"继承了",
            r"子类",
            r"class hierarchy",
            r"type hierarchy",
        ]
        for pattern in inherit_patterns:
            if re.search(pattern, q):
                return "inheritance"

        return "entity"

    # ------------------------------------------------------------------
    # Search term extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_search_terms(query: str) -> List[str]:
        """Extract potential code symbol names from a query.

        Uses heuristics: CamelCase splitting, snake_case splitting,
        and filtering of common stop words.
        """
        # Remove query mode keywords
        stop_words = {
            "who",
            "what",
            "calls",
            "invokes",
            "implements",
            "extends",
            "from",
            "the",
            "of",
            "is",
            "are",
            "does",
            "do",
            "a",
            "an",
            "call",
            "chain",
            "graph",
            "class",
            "hierarchy",
            "type",
            "subclasses",
            "implementations",
            "inherits",
            "inheritance",
            "的",
            "了",
            "是",
            "在",
            "调用",
            "实现",
            "继承",
            "谁",
            "什么",
        }

        # Extract CamelCase and snake_case tokens
        # CamelCase: "UserService" -> ["User", "Service"]
        # snake_case: "process_payment" -> ["process", "payment"]
        # dot.notation: "os.path.join" -> ["os", "path", "join"]
        tokens: Set[str] = set()

        # Split by whitespace and common delimiters
        for word in re.split(r'[\s,;:!?()[\]{}\'"]+', query):
            if not word:
                continue

            # CamelCase splitting
            camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", word)
            if camel_parts and len(camel_parts) > 1:
                tokens.update(
                    p.lower() for p in camel_parts if p.lower() not in stop_words
                )
                # Also add the full CamelCase name
                tokens.add(word.lower())

            # snake_case splitting
            if "_" in word:
                parts = word.split("_")
                tokens.update(p.lower() for p in parts if p.lower() not in stop_words)
                tokens.add(word.lower())

            # dot.notation splitting
            if "." in word:
                parts = word.split(".")
                tokens.update(p.lower() for p in parts if p.lower() not in stop_words)

            # Single word
            if word.lower() not in stop_words and len(word) > 1:
                tokens.add(word.lower())

        return list(tokens)

    # ------------------------------------------------------------------
    # Node matching
    # ------------------------------------------------------------------

    def _find_matching_nodes(self, terms: List[str]) -> List[Vertex]:
        """Find graph nodes matching the search terms.

        Scoring: exact name match = 3, name contains term = 2,
        vid contains term = 1. Return top-scored unique nodes.
        """
        scored: Dict[str, Tuple[Vertex, int]] = {}

        for term in terms:
            # Exact name match
            for v in self._name_index.get(term, []):
                if v.vid not in scored or scored[v.vid][1] < 3:
                    scored[v.vid] = (v, 3)

            # Name contains term
            for name_lower, vertices in self._name_index.items():
                if term in name_lower and name_lower != term:
                    for v in vertices:
                        if v.vid not in scored or scored[v.vid][1] < 2:
                            scored[v.vid] = (v, 2)

            # VID contains term
            for vid, v in self._vid_index.items():
                if term in vid.lower() and vid not in scored:
                    scored[vid] = (v, 1)

        # Sort by score descending, take top_k
        sorted_nodes = sorted(scored.values(), key=lambda x: -x[1])
        return [v for v, _ in sorted_nodes[: self._top_k]]

    # ------------------------------------------------------------------
    # Graph expansion
    # ------------------------------------------------------------------

    def _expand_bfs(
        self,
        seed_nodes: List[Vertex],
        depth: Optional[int] = None,
        direction: Direction = Direction.BOTH,
    ) -> MemoryGraph:
        """BFS expansion from seed nodes.

        Traverses edges with priority: contains > calls/inheritance > imports.
        """
        if depth is None:
            depth = self._bfs_depth

        subgraph = MemoryGraph()
        visited: Set[str] = set()
        queue: deque = deque()  # (vertex, current_depth)

        for v in seed_nodes:
            subgraph.upsert_vertex(v)
            visited.add(v.vid)
            queue.append((v.vid, 0))

        while queue and subgraph.vertex_count < self._max_subgraph_nodes:
            vid, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            # Get neighbor edges sorted by priority
            try:
                edges = list(self._graph.get_neighbor_edges(vid, direction))
            except (KeyError, StopIteration):
                continue

            # Sort by edge priority
            edges.sort(
                key=lambda e: _EDGE_PRIORITY.get(e.name, 0),
                reverse=True,
            )

            for edge in edges:
                if subgraph.edge_count > self._max_subgraph_nodes * 3:
                    break

                # Add edge to subgraph
                subgraph.append_edge(edge)

                # Add neighbor vertex
                neighbor_id = edge.nid(vid)
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    try:
                        neighbor = self._graph.get_vertex(neighbor_id)
                        subgraph.upsert_vertex(neighbor)
                        queue.append((neighbor_id, current_depth + 1))
                    except KeyError:
                        pass

        return subgraph

    def _expand_call_chain(
        self,
        seed_nodes: List[Vertex],
        reverse: bool = True,
    ) -> MemoryGraph:
        """Expand call chain from seed nodes.

        Args:
            seed_nodes: Starting nodes (typically functions/methods).
            reverse: If True, find callers (IN direction on CALLS edges).
                     If False, find callees (OUT direction on CALLS edges).
        """
        subgraph = MemoryGraph()
        visited: Set[str] = set()
        queue: deque = deque()

        for v in seed_nodes:
            subgraph.upsert_vertex(v)
            visited.add(v.vid)
            queue.append((v.vid, 0))

        direction = Direction.IN if reverse else Direction.OUT

        while queue and subgraph.vertex_count < self._max_subgraph_nodes:
            vid, current_depth = queue.popleft()

            if current_depth >= self._bfs_depth:
                continue

            try:
                edges = list(self._graph.get_neighbor_edges(vid, direction))
            except (KeyError, StopIteration):
                continue

            for edge in edges:
                if edge.name != CodeEdgeType.CALLS.value:
                    continue

                subgraph.append_edge(edge)

                neighbor_id = edge.nid(vid)
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    try:
                        neighbor = self._graph.get_vertex(neighbor_id)
                        subgraph.upsert_vertex(neighbor)
                        queue.append((neighbor_id, current_depth + 1))
                    except KeyError:
                        pass

        # Also add containment edges for context
        self._add_containment_edges(subgraph)

        return subgraph

    def _expand_inheritance(self, seed_nodes: List[Vertex]) -> MemoryGraph:
        """Expand inheritance hierarchy from seed nodes."""
        subgraph = MemoryGraph()
        visited: Set[str] = set()
        queue: deque = deque()

        for v in seed_nodes:
            subgraph.upsert_vertex(v)
            visited.add(v.vid)
            queue.append((v.vid, 0))

        while queue and subgraph.vertex_count < self._max_subgraph_nodes:
            vid, current_depth = queue.popleft()

            if current_depth >= self._bfs_depth:
                continue

            try:
                edges = list(self._graph.get_neighbor_edges(vid, Direction.BOTH))
            except (KeyError, StopIteration):
                continue

            for edge in edges:
                if edge.name not in (
                    CodeEdgeType.INHERITS.value,
                    CodeEdgeType.IMPLEMENTS.value,
                    CodeEdgeType.CONTAINS.value,
                ):
                    continue

                subgraph.append_edge(edge)

                neighbor_id = edge.nid(vid)
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    try:
                        neighbor = self._graph.get_vertex(neighbor_id)
                        subgraph.upsert_vertex(neighbor)
                        queue.append((neighbor_id, current_depth + 1))
                    except KeyError:
                        pass

        return subgraph

    def _add_containment_edges(self, subgraph: MemoryGraph):
        """Add CONTAINS edges for vertices already in the subgraph."""
        for v in list(subgraph.vertices()):
            try:
                for edge in self._graph.get_neighbor_edges(v.vid, Direction.OUT):
                    if edge.name == CodeEdgeType.CONTAINS.value:
                        if subgraph.has_vertex(edge.tid):
                            subgraph.append_edge(edge)
            except (KeyError, StopIteration):
                pass

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_subgraph(
        self,
        subgraph: MemoryGraph,
        mode: str,
        query: str,
    ) -> List[Chunk]:
        """Format the subgraph as text chunks for RAG context."""
        if subgraph.vertex_count == 0:
            return []

        # Group vertices by type
        by_type: Dict[str, List[Vertex]] = {}
        for v in subgraph.vertices():
            ntype = v.get_prop("node_type") or v.get_prop("type") or "unknown"
            if ntype not in by_type:
                by_type[ntype] = []
            by_type[ntype].append(v)

        # Build structured text
        lines: List[str] = []
        lines.append(f"# Code Graph Query: {query}")
        lines.append(f"Mode: {mode}")
        lines.append("")

        # Classes and their methods
        if CodeNodeType.CLASS.value in by_type:
            lines.append("## Classes")
            for cls in by_type[CodeNodeType.CLASS.value]:
                source = cls.get_prop("source_file") or cls.get_prop("file_path") or ""
                location = (
                    cls.get_prop("source_location") or cls.get_prop("start_line") or ""
                )
                lines.append(f"- **{cls.name}** ({source} {location})")

                # Find methods of this class
                for edge in subgraph.edges():
                    if (
                        edge.sid == cls.vid
                        and edge.name == CodeEdgeType.CONTAINS.value
                        and subgraph.has_vertex(edge.tid)
                    ):
                        method = subgraph.get_vertex(edge.tid)
                        mtype = (
                            method.get_prop("node_type")
                            or method.get_prop("type")
                            or ""
                        )
                        if mtype in (
                            CodeNodeType.METHOD.value,
                            CodeNodeType.FUNCTION.value,
                        ):
                            lines.append(f"  - {method.name}()")

                # Inheritance
                for edge in subgraph.edges():
                    if edge.sid == cls.vid and edge.name in (
                        CodeEdgeType.INHERITS.value,
                        CodeEdgeType.IMPLEMENTS.value,
                    ):
                        if subgraph.has_vertex(edge.tid):
                            parent = subgraph.get_vertex(edge.tid)
                            lines.append(f"  - {edge.name} -> {parent.name}")
            lines.append("")

        # Functions
        if CodeNodeType.FUNCTION.value in by_type:
            lines.append("## Functions")
            for func in by_type[CodeNodeType.FUNCTION.value]:
                source = (
                    func.get_prop("source_file") or func.get_prop("file_path") or ""
                )
                location = (
                    func.get_prop("source_location")
                    or func.get_prop("start_line")
                    or ""
                )
                lines.append(f"- **{func.name}()** ({source} {location})")
            lines.append("")

        # Methods (if not already shown under classes)
        if CodeNodeType.METHOD.value in by_type:
            shown_methods: Set[str] = set()
            # Methods shown under their class are already listed
            for cls in by_type.get(CodeNodeType.CLASS.value, []):
                for edge in subgraph.edges():
                    if (
                        edge.sid == cls.vid
                        and edge.name == CodeEdgeType.CONTAINS.value
                        and subgraph.has_vertex(edge.tid)
                    ):
                        shown_methods.add(edge.tid)

            orphan_methods = [
                m
                for m in by_type[CodeNodeType.METHOD.value]
                if m.vid not in shown_methods
            ]
            if orphan_methods:
                lines.append("## Methods")
                for method in orphan_methods:
                    source = (
                        method.get_prop("source_file")
                        or method.get_prop("file_path")
                        or ""
                    )
                    location = (
                        method.get_prop("source_location")
                        or method.get_prop("start_line")
                        or ""
                    )
                    lines.append(f"- **{method.name}()** ({source} {location})")
                lines.append("")

        # Call relationships
        call_edges = [e for e in subgraph.edges() if e.name == CodeEdgeType.CALLS.value]
        if call_edges:
            lines.append("## Call Relationships")
            for edge in call_edges:
                conf = edge.get_prop("confidence") or ""
                try:
                    src = subgraph.get_vertex(edge.sid)
                    tgt = subgraph.get_vertex(edge.tid)
                    lines.append(f"- {src.name}() -> {tgt.name}() [{conf}]")
                except KeyError:
                    pass
            lines.append("")

        # Modules
        if CodeNodeType.MODULE.value in by_type:
            lines.append("## Modules")
            for mod in by_type[CodeNodeType.MODULE.value]:
                source = mod.get_prop("source_file") or mod.get_prop("file_path") or ""
                if source and source != "external":
                    lines.append(f"- {mod.name} ({source})")
                elif source == "external":
                    lines.append(f"- {mod.name} (external)")
            lines.append("")

        # Create a single Chunk with the formatted context
        content = "\n".join(lines)
        chunk = Chunk(
            content=content,
            metadata={
                "retriever": "code_graph",
                "knowledge_id": self._knowledge_id,
                "query_mode": mode,
                "query": query,
                "graph_vertices": subgraph.vertex_count,
                "graph_edges": subgraph.edge_count,
                "score": 1.0,  # Graph retrieval doesn't have a score
            },
        )

        return [chunk]
