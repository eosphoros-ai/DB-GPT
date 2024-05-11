"""TuGraph vector store."""
import logging
from typing import Any, List, Optional, Tuple

from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase
from dbgpt.storage.graph_store.graph import Direction, Edge, MemoryGraph, Vertex

logger = logging.getLogger(__name__)


def _format_paths(paths):
    formatted_paths = []
    for path in paths:
        formatted_path = []
        nodes = list(path["p"].nodes)
        rels = list(path["p"].relationships)
        for i in range(len(nodes)):
            formatted_path.append(nodes[i]._properties["id"])
            if i < len(rels):
                formatted_path.append(rels[i]._properties["id"])
        formatted_paths.append(formatted_path)
    return formatted_paths


def _remove_duplicates(lst):
    seen = set()
    result = []
    for sub_lst in lst:
        sub_tuple = tuple(sub_lst)
        if sub_tuple not in seen:
            result.append(sub_lst)
            seen.add(sub_tuple)
    return result


def _process_data(data):
    nodes = {}
    edges = {}

    def add_vertex(vid):
        if vid not in nodes:
            nodes[vid] = Vertex(vid)

    def add_edge(sid, tid, prop_id):
        edge_key = (sid, tid, prop_id)

        if edge_key not in edges:
            edges[edge_key] = Edge(sid, tid, label=prop_id)

    for item in data:
        sid = item[0]
        i = 1
        while i < len(item) - 1:
            prop_id = item[i]
            tid = item[i + 1]
            add_vertex(sid)
            add_vertex(tid)
            add_edge(sid, tid, prop_id)
            i += 2

    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


class TuGraphStore(GraphStoreBase):
    """TuGraph vector store."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        pwd: str,
        db_name: str,
        node_label: str = "entity",
        edge_label: str = "rel",
        **kwargs: Any,
    ) -> None:
        """Initialize the TuGraphStore with connection details."""
        self.conn = TuGraphConnector.from_uri_db(
            host=host, port=port, user=user, pwd=pwd, db_name=db_name
        )
        self._node_label = node_label
        self._edge_label = edge_label
        self._create_schema()

    def _check_label(self, type: str):
        result = self.conn.get_table_names()
        if type == "vertex":
            return self._node_label in result["vertex_tables"]
        if type == "edge":
            return self._edge_label in result["edge_tables"]

    def _create_schema(self):
        if not self._check_label("vertex"):
            create_vertex_gql = (
                f"CALL db.createLabel("
                f"'vertex', '{self._node_label}', "
                f"'id', ['id',string,false])"
            )
            self.conn.run(create_vertex_gql)
        if not self._check_label("edge"):
            create_edge_gql = f"""CALL db.createLabel(
                'edge', '{self._edge_label}', '[["{self._node_label}",
                "{self._node_label}"]]', ["id",STRING,false])"""
            self.conn.run(create_edge_gql)

    def get_triplets(self, subj: str) -> List[Tuple[str, str]]:
        """Get triplets."""
        query = (
            f"MATCH (n1:{self._node_label})-[r]->(n2:{self._node_label}) "
            f'WHERE n1.id = "{subj}" RETURN r.id as rel, n2.id as obj;'
        )
        data = self.conn.run(query)
        return [(record["rel"], record["obj"]) for record in data]

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        subj_query = f"""MERGE (n1:{self._node_label} {{id:'{subj}'}})"""
        obj_query = f"MERGE (n1:{self._node_label} {{id:'{obj}'}})"
        rel_query = (
            f"MERGE (n1:{self._node_label} {{id:'{subj}'}})"
            f"-[r:{self._edge_label} {{id:'{rel}'}}]->"
            f"(n2:{self._node_label} {{id:'{obj}'}})"
        )
        self.conn.run(query=subj_query)
        self.conn.run(query=obj_query)
        self.conn.run(query=rel_query)

    def get_rel_map(
        self, subjs: Optional[List[str]] = None, depth: int = 2, limit: int = 30
    ) -> List[List[str]]:
        """Get flat rel map."""
        # *1..{depth}
        query = (
            f"MATCH p=(n:{self._node_label})"
            f"-[r:{self._edge_label}*1..{depth}]->() "
            f"WHERE n.id IN {subjs} RETURN p LIMIT {limit}"
        )
        data = self.conn.run(query=query)
        result = []
        formatted_paths = _format_paths(data)
        for path in formatted_paths:
            result.append(path)
        # result = _remove_duplicates(result)
        return result

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        del_query = (
            f"MATCH (n1:{self._node_label} {{id:'{sub}'}})"
            f"-[r:{self._edge_label} {{id:'{rel}'}}]->"
            f"(n2:{self._node_label} {{id:'{obj}'}}) DELETE n1,n2,r"
        )
        self.conn.run(query=del_query)

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        query = "CALL dbms.graph.getGraphSchema()"
        data = self.conn.run(query=query)
        schema = data[0]["schema"]
        return schema

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = None,
        fan: int = None,
        limit: int = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if fan is not None:
            raise ValueError("Fan functionality is not supported at this time.")
        else:
            query = (
                f"MATCH p=(n:{self._node_label})"
                f"-[r:{self._edge_label}*1..{depth}]-() "
                f"WHERE n.id IN {subs} RETURN p LIMIT {limit}"
            )
            data = self.conn.run(query=query)
            result = []
            formatted_paths = _format_paths(data)
            for path in formatted_paths:
                result.append(path)
            graph = _process_data(result)
            mg = MemoryGraph()
            for vertex in graph["nodes"]:
                mg.upsert_vertex(vertex)
            for edge in graph["edges"]:
                mg.append_edge(edge)
            return mg

    def query(self, query: str, **args) -> MemoryGraph:
        """Execute a query on graph."""
        self.conn.run(query=query)
        # todo: construct MemoryGraph
        return MemoryGraph()
