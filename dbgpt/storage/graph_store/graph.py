"""Graph store base class."""
import itertools
import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from typing import Any, List, Dict, Set, Iterator

import networkx as nx

logger = logging.getLogger(__name__)


class Direction(Enum):
    OUT = 0
    IN = 1
    BOTH = 2


class Elem(ABC):
    """Elem class"""

    def __init__(self):
        self._props = {}

    @property
    def props(self) -> Dict[str, Any]:
        return self._props

    def set_prop(self, key: str, value: Any):
        self._props[key] = value

    def get_prop(self, key: str):
        return self._props.get(key)

    def del_prop(self, key: str):
        self._props.pop(key, None)

    def has_props(self, **props):
        return all(self._props.get(k) == v for k, v in props.items())


class Vertex(Elem):
    """Vertex class."""

    def __init__(self, vid: str, **props):
        super().__init__()
        self._vid = vid
        for k, v in props:
            self.set_prop(k, v)

    @property
    def vid(self) -> str:
        return self._vid

    def __str__(self):
        return f"({self._vid})"


class Edge(Elem):
    """Edge class."""

    def __init__(self, sid: str, tid: str, **props):
        super().__init__()
        self._sid = sid
        self._tid = tid
        for k, v in props.items():
            self.set_prop(k, v)

    @property
    def sid(self) -> str:
        return self._sid

    @property
    def tid(self) -> str:
        return self._tid

    def nid(self, vid):
        """return neighbor id"""
        if vid == self._sid:
            return self._tid
        elif vid == self._tid:
            return self._sid
        else:
            raise ValueError(f"Get nid of {vid} on {self} failed")

    def __iter__(self):
        values = self._props.values()
        if len(values) > 1:
            raise ValueError(f"Cast triplet: too many props of {self}")

        yield self._sid
        yield str(next(iter(values))) if values else ""
        yield self._tid

    def __str__(self):
        return f"({self._sid})->({self._tid})"


class Graph(ABC):
    @abstractmethod
    def upsert_vertex(self, vertex: Vertex):
        """Add a vertex."""

    @abstractmethod
    def append_edge(self, edge: Edge):
        """Add an edge."""

    @abstractmethod
    def get_vertex(self, vid: str) -> Vertex:
        """Get a vertex."""

    @abstractmethod
    def get_neighbor_edges(
        self,
        vid: str,
        direction: Direction = Direction.OUT
    ) -> List[Edge]:
        """Get neighbor edges"""

    @abstractmethod
    def del_vertices(self, *vids: str):
        """Delete vertices and their neighbor edges."""

    @abstractmethod
    def del_edges(self, sid: str, tid: str, **props):
        """Delete edges(sid -> tid) matches props."""

    @abstractmethod
    def del_neighbor_edges(
        self,
        vid: str,
        direction: Direction = Direction.OUT
    ):
        """Delete neighbor edges."""

    @abstractmethod
    def search(
        self,
        vids: List[str],
        direction: Direction = Direction.OUT,
        depth_limit: int = None,
        fan_limit: int = None,
        result_limit: int = None
    ) -> "Graph":
        """Breadth-first search."""


class MemoryGraph(Graph):
    """Graph class."""

    def __init__(self):
        """init vertices, out edges, in edges index"""
        self._vs = defaultdict()
        self._oes = defaultdict(lambda: defaultdict(set))
        self._ies = defaultdict(lambda: defaultdict(set))
        self._edge_count = 0

    @property
    def vertex_count(self):
        return len(self._vs)

    @property
    def edge_count(self):
        return self._edge_count

    def upsert_vertex(self, vertex: Vertex):
        self._vs[vertex.vid] = vertex

    def append_edge(self, edge: Edge):
        sid = edge.sid
        tid = edge.tid

        if edge in self._oes[sid][tid]:
            return False

        # construct vertex index
        self._vs.setdefault(sid, Vertex(sid))
        self._vs.setdefault(tid, Vertex(tid))

        # construct edge index
        self._oes[sid][tid].add(edge)
        self._ies[tid][sid].add(edge)
        self._edge_count += 1

        return True

    def get_vertex(self, vid: str) -> Vertex:
        return self._vs[vid]

    def get_neighbor_edges(
        self,
        vid: str,
        direction: Direction = Direction.OUT,
        limit: int = None
    ) -> Iterator[Edge]:
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
            es = (e for e in es if e not in seen and not seen.add(e))

        else:
            raise ValueError(f"Invalid direction: {direction}")

        return itertools.islice(es, limit) if limit else es

    def del_vertices(self, *vids: str):
        for vid in vids:
            self.del_neighbor_edges(vid, Direction.BOTH)
            self._vs.pop(vid, None)

    def del_edges(self, sid: str, tid: str, **props):
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

        self._edge_count -= (old_edge_cnt - len(self._oes[sid][tid]))

    def del_neighbor_edges(
        self,
        vid: str,
        direction: Direction = Direction.OUT
    ):
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
        direction: Direction = Direction.OUT,
        depth_limit: int = None,
        fan_limit: int = None,
        result_limit: int = None
    ) -> "MemoryGraph":
        subgraph = MemoryGraph()

        for vid in vids:
            self.__search(
                vid,
                direction,
                depth_limit,
                fan_limit,
                result_limit,
                0,
                set(),
                subgraph
            )

        return subgraph

    def __search(
        self,
        vid: str,
        direction: Direction,
        depth_limit: int,
        fan_limit: int,
        result_limit: int,
        depth: int,
        visited: Set,
        subgraph: "MemoryGraph"
    ):
        if vid in visited or depth_limit and depth >= depth_limit:
            return

        # visit vertex
        subgraph.upsert_vertex(self.get_vertex(vid))
        visited.add(vid)

        # visit edges
        nids = set()
        for edge in self.get_neighbor_edges(vid, direction, fan_limit):
            if result_limit and subgraph.edge_count >= result_limit:
                return

            # append edge success then visit new vertex
            if subgraph.append_edge(edge):
                nid = edge.nid(vid)
                if nid not in visited:
                    nids.add(nid)

        # next hop
        for nid in nids:
            self.__search(
                nid,
                direction,
                depth_limit,
                fan_limit,
                result_limit,
                depth + 1,
                visited,
                subgraph
            )

    def vertices(self) -> Iterator[Vertex]:
        return iter(self._vs.values())

    def edges(self) -> Iterator[Edge]:
        return iter(
            e for nbs in self._oes.values() for es in nbs.values() for e in es
        )

    def graphviz(self, name='g'):
        """View graphviz graph: https://dreampuf.github.io/GraphvizOnline"""
        g = nx.MultiDiGraph()
        for vertex in self.vertices():
            g.add_node(vertex.vid)

        for edge in self.edges():
            triplet = tuple(edge)
            g.add_edge(triplet[0], triplet[2], label=triplet[1])

        digraph = nx.nx_agraph.to_agraph(g).to_string()
        digraph = digraph.replace('digraph ""', f"digraph {name}")
        digraph = re.sub(r"key=\d+,?\s*", "", digraph)
        return digraph
