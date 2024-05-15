"""Graph store base class."""
import itertools
import json
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)


class Direction(Enum):
    """Direction class."""

    OUT = 0
    IN = 1
    BOTH = 2


class Elem(ABC):
    """Elem class."""

    def __init__(self):
        """Initialize Elem."""
        self._props = {}

    @property
    def props(self) -> Dict[str, Any]:
        """Get all the properties of Elem."""
        return self._props

    def set_prop(self, key: str, value: Any):
        """Set a property of ELem."""
        self._props[key] = value

    def get_prop(self, key: str):
        """Get one of the properties of Elem."""
        return self._props.get(key)

    def del_prop(self, key: str):
        """Delete a property of ELem."""
        self._props.pop(key, None)

    def has_props(self, **props):
        """Check if the element has the specified properties with the given values."""
        return all(self._props.get(k) == v for k, v in props.items())

    @abstractmethod
    def format(self, label_key: Optional[str] = None):
        """Format properties into a string."""
        formatted_props = [
            f"{k}:{json.dumps(v)}" for k, v in self._props.items() if k != label_key
        ]
        return f"{{{';'.join(formatted_props)}}}"


class Vertex(Elem):
    """Vertex class."""

    def __init__(self, vid: str, **props):
        """Initialize Vertex."""
        super().__init__()
        self._vid = vid
        for k, v in props.items():
            self.set_prop(k, v)

    @property
    def vid(self) -> str:
        """Return the vertex ID."""
        return self._vid

    def format(self, label_key: Optional[str] = None):
        """Format vertex properties into a string."""
        label = self.get_prop(label_key) if label_key else self._vid
        props_str = super().format(label_key)
        if props_str == "{}":
            return f"({label})"
        else:
            return f"({label}:{props_str})"

    def __str__(self):
        """Return the vertex ID as its string representation."""
        return f"({self._vid})"


class Edge(Elem):
    """Edge class."""

    def __init__(self, sid: str, tid: str, **props):
        """Initialize Edge."""
        super().__init__()
        self._sid = sid
        self._tid = tid
        for k, v in props.items():
            self.set_prop(k, v)

    @property
    def sid(self) -> str:
        """Return the source vertex ID of the edge."""
        return self._sid

    @property
    def tid(self) -> str:
        """Return the target vertex ID of the edge."""
        return self._tid

    def nid(self, vid):
        """Return neighbor id."""
        if vid == self._sid:
            return self._tid
        elif vid == self._tid:
            return self._sid
        else:
            raise ValueError(f"Get nid of {vid} on {self} failed")

    def format(self, label_key: Optional[str] = None):
        """Format the edge properties into a string."""
        label = self.get_prop(label_key) if label_key else ""
        props_str = super().format(label_key)
        if props_str == "{}":
            return f"-[{label}]->" if label else "->"
        else:
            return f"-[{label}:{props_str}]->" if label else f"-[{props_str}]->"

    def triplet(self, label_key: str) -> Tuple[str, str, str]:
        """Return a triplet."""
        assert label_key, "label key is needed"
        return self._sid, str(self.get_prop(label_key)), self._tid

    def __str__(self):
        """Return the edge '(sid)->(tid)'."""
        return f"({self._sid})->({self._tid})"


class Graph(ABC):
    """Graph class."""

    @abstractmethod
    def upsert_vertex(self, vertex: Vertex):
        """Add a vertex."""

    @abstractmethod
    def append_edge(self, edge: Edge):
        """Add an edge."""

    @abstractmethod
    def has_vertex(self, vid: str) -> bool:
        """Check vertex exists."""

    @abstractmethod
    def get_vertex(self, vid: str) -> Vertex:
        """Get a vertex."""

    @abstractmethod
    def get_neighbor_edges(
        self,
        vid: str,
        direction: Direction = Direction.OUT,
        limit: Optional[int] = None,
    ) -> Iterator[Edge]:
        """Get neighbor edges."""

    @abstractmethod
    def vertices(self) -> Iterator[Vertex]:
        """Get vertex iterator."""

    @abstractmethod
    def edges(self) -> Iterator[Edge]:
        """Get edge iterator."""

    @abstractmethod
    def del_vertices(self, *vids: str):
        """Delete vertices and their neighbor edges."""

    @abstractmethod
    def del_edges(self, sid: str, tid: str, **props):
        """Delete edges(sid -> tid) matches props."""

    @abstractmethod
    def del_neighbor_edges(self, vid: str, direction: Direction = Direction.OUT):
        """Delete neighbor edges."""

    @abstractmethod
    def search(
        self,
        vids: List[str],
        direct: Direction = Direction.OUT,
        depth: Optional[int] = None,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> "Graph":
        """Search on graph."""

    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """Get schema."""

    @abstractmethod
    def format(self) -> str:
        """Format graph data to string."""


class MemoryGraph(Graph):
    """Graph class."""

    def __init__(self, vertex_label: Optional[str] = None, edge_label: str = "label"):
        """Initialize MemoryGraph with vertex label and edge label."""
        assert edge_label, "Edge label is needed"

        # metadata
        self._vertex_label = vertex_label
        self._edge_label = edge_label
        self._vertex_prop_keys = {vertex_label} if vertex_label else set()
        self._edge_prop_keys = {edge_label}
        self._edge_count = 0

        # init vertices, out edges, in edges index
        self._vs: Any = defaultdict()
        self._oes: Any = defaultdict(lambda: defaultdict(set))
        self._ies: Any = defaultdict(lambda: defaultdict(set))

    @property
    def vertex_label(self):
        """Return the label for vertices."""
        return self._vertex_label

    @property
    def edge_label(self):
        """Return the label for edges."""
        return self._edge_label

    @property
    def vertex_prop_keys(self):
        """Return a set of property keys for vertices."""
        return self._vertex_prop_keys

    @property
    def edge_prop_keys(self):
        """Return a set of property keys for edges."""
        return self._edge_prop_keys

    @property
    def vertex_count(self):
        """Return the number of vertices in the graph."""
        return len(self._vs)

    @property
    def edge_count(self):
        """Return the count of edges in the graph."""
        return self._edge_count

    def upsert_vertex(self, vertex: Vertex):
        """Insert or update a vertex based on its ID."""
        if vertex.vid in self._vs:
            self._vs[vertex.vid].props.update(vertex.props)
        else:
            self._vs[vertex.vid] = vertex

        # update metadata
        self._vertex_prop_keys.update(vertex.props.keys())

    def append_edge(self, edge: Edge):
        """Append an edge if it doesn't exist; requires edge label."""
        if self.edge_label not in edge.props.keys():
            raise ValueError(f"Edge prop '{self.edge_label}' is needed")

        sid = edge.sid
        tid = edge.tid

        if edge in self._oes[sid][tid]:
            return False

        # init vertex index
        self._vs.setdefault(sid, Vertex(sid))
        self._vs.setdefault(tid, Vertex(tid))

        # update edge index
        self._oes[sid][tid].add(edge)
        self._ies[tid][sid].add(edge)

        # update metadata
        self._edge_prop_keys.update(edge.props.keys())
        self._edge_count += 1
        return True

    def has_vertex(self, vid: str) -> bool:
        """Retrieve a vertex by ID."""
        return vid in self._vs

    def get_vertex(self, vid: str) -> Vertex:
        """Retrieve a vertex by ID."""
        return self._vs[vid]

    def get_neighbor_edges(
        self,
        vid: str,
        direction: Direction = Direction.OUT,
        limit: Optional[int] = None,
    ) -> Iterator[Edge]:
        """Get edges connected to a vertex by direction."""
        if direction == Direction.OUT:
            es = (e for es in self._oes[vid].values() for e in es)

        elif direction == Direction.IN:
            es = iter(e for es in self._ies[vid].values() for e in es)

        elif direction == Direction.BOTH:
            oes = (e for es in self._oes[vid].values() for e in es)
            ies = (e for es in self._ies[vid].values() for e in es)

            # merge
            tuples = itertools.zip_longest(oes, ies)
            es = (e for t in tuples for e in t if e is not None)

            # distinct
            seen = set()

            # es = (e for e in es if e not in seen and not seen.add(e))
            def unique_elements(elements):
                for element in elements:
                    if element not in seen:
                        seen.add(element)
                        yield element

            es = unique_elements(es)
        else:
            raise ValueError(f"Invalid direction: {direction}")

        return itertools.islice(es, limit) if limit else es

    def vertices(self) -> Iterator[Vertex]:
        """Return vertices."""
        return iter(self._vs.values())

    def edges(self) -> Iterator[Edge]:
        """Return edges."""
        return iter(e for nbs in self._oes.values() for es in nbs.values() for e in es)

    def del_vertices(self, *vids: str):
        """Delete specified vertices."""
        for vid in vids:
            self.del_neighbor_edges(vid, Direction.BOTH)
            self._vs.pop(vid, None)

    def del_edges(self, sid: str, tid: str, **props):
        """Delete edges."""
        old_edge_cnt = len(self._oes[sid][tid])

        if not props:
            self._edge_count -= old_edge_cnt
            self._oes[sid].pop(tid, None)
            self._ies[tid].pop(sid, None)
            return

        def remove_matches(es):
            return set(filter(lambda e: not e.has_props(**props), es))

        self._oes[sid][tid] = remove_matches(self._oes[sid][tid])
        self._ies[tid][sid] = remove_matches(self._ies[tid][sid])

        self._edge_count -= old_edge_cnt - len(self._oes[sid][tid])

    def del_neighbor_edges(self, vid: str, direction: Direction = Direction.OUT):
        """Delete all neighbor edges."""

        def del_index(idx, i_idx):
            for nid in idx[vid].keys():
                self._edge_count -= len(i_idx[nid][vid])
                i_idx[nid].pop(vid, None)
            idx.pop(vid, None)

        if direction in [Direction.OUT, Direction.BOTH]:
            del_index(self._oes, self._ies)

        if direction in [Direction.IN, Direction.BOTH]:
            del_index(self._ies, self._oes)

    def search(
        self,
        vids: List[str],
        direct: Direction = Direction.OUT,
        depth: Optional[int] = None,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> "MemoryGraph":
        """Search the graph from a vertex with specified parameters."""
        subgraph = MemoryGraph()

        for vid in vids:
            self.__search(vid, direct, depth, fan, limit, 0, set(), subgraph)

        return subgraph

    def __search(
        self,
        vid: str,
        direct: Direction,
        depth: Optional[int],
        fan: Optional[int],
        limit: Optional[int],
        _depth: int,
        _visited: Set,
        _subgraph: "MemoryGraph",
    ):
        if vid in _visited or depth and _depth >= depth:
            return

        # visit vertex
        if not self.has_vertex(vid):
            return
        _subgraph.upsert_vertex(self.get_vertex(vid))
        _visited.add(vid)

        # visit edges
        nids = set()
        for edge in self.get_neighbor_edges(vid, direct, fan):
            if limit and _subgraph.edge_count >= limit:
                return

            # append edge success then visit new vertex
            if _subgraph.append_edge(edge):
                nid = edge.nid(vid)
                if nid not in _visited:
                    nids.add(nid)

        # next hop
        for nid in nids:
            self.__search(
                nid, direct, depth, fan, limit, _depth + 1, _visited, _subgraph
            )

    def schema(self) -> Dict[str, Any]:
        """Return schema."""
        return {
            "schema": [
                {
                    "type": "VERTEX",
                    "label": f"{self._vertex_label}",
                    "properties": [{"name": k} for k in self._vertex_prop_keys],
                },
                {
                    "type": "EDGE",
                    "label": f"{self._edge_label}",
                    "properties": [{"name": k} for k in self._edge_prop_keys],
                },
            ]
        }

    def format(self) -> str:
        """Format graph to string."""
        vs_str = "\n".join(v.format(self.vertex_label) for v in self.vertices())
        es_str = "\n".join(
            f"{self.get_vertex(e.sid).format(self.vertex_label)}"
            f"{e.format(self.edge_label)}"
            f"{self.get_vertex(e.tid).format(self.vertex_label)}"
            for e in self.edges()
        )
        return f"Vertices:\n{vs_str}\n\nEdges:\n{es_str}"

    def graphviz(self, name="g"):
        """View graphviz graph: https://dreampuf.github.io/GraphvizOnline."""
        g = nx.MultiDiGraph()
        for vertex in self.vertices():
            g.add_node(vertex.vid)

        for edge in self.edges():
            triplet = edge.triplet(self.edge_label)
            g.add_edge(triplet[0], triplet[2], label=triplet[1])

        digraph = nx.nx_agraph.to_agraph(g).to_string()
        digraph = digraph.replace('digraph ""', f"digraph {name}")
        digraph = re.sub(r"key=\d+,?\s*", "", digraph)
        return digraph
