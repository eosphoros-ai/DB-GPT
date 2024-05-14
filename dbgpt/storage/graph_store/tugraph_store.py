"""TuGraph vector store."""
import logging
from typing import Any, Optional
from typing import List
from typing import Tuple

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Direction
from dbgpt.storage.graph_store.graph import Edge, MemoryGraph
from dbgpt.storage.graph_store.graph import Vertex

logger = logging.getLogger(__name__)


class TuGraphStoreConfig(GraphStoreConfig):
    """TuGraph store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: str = Field(
        default="127.0.0.1",
        description="TuGraph host",
    )
    port: int = Field(
        default=7070,
        description="TuGraph port",
    )
    username: str = Field(
        default="admin",
        description="login username",
    )
    password: str = Field(
        default="73@TuGraph",
        description="login password",
    )
    vertex_type: str = Field(
        default="entity",
        description="The type of graph vertex, `entity` by default.",
    )
    edge_type: str = Field(
        default="relation",
        description="The type of graph edge, `relation` by default.",
    )
    edge_name_key: str = Field(
        default="label",
        description="The label of edge name, `label` by default.",
    )


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


def _format_query_data(data):
    node_ids_set = set()
    rels_set = set()
    from neo4j import graph

    for record in data:
        for key in record.keys():
            value = record[key]
            if isinstance(value, graph.Node):
                node_id = value._properties["id"]
                node_ids_set.add(node_id)
            elif isinstance(value, graph.Relationship):
                rel_nodes = value.nodes
                prop_id = value._properties["id"]
                src_id = rel_nodes[0]._properties["id"]
                dst_id = rel_nodes[1]._properties["id"]
                rels_set.add((src_id, dst_id, prop_id))
            elif isinstance(value, graph.Path):
                formatted_paths = _format_paths(data)
                for path in formatted_paths:
                    for i in range(0, len(path), 2):
                        node_ids_set.add(path[i])
                        if i + 2 < len(path):
                            rels_set.add((path[i], path[i + 2], path[i + 1]))

    nodes = [Vertex(node_id) for node_id in node_ids_set]
    rels = [
        Edge(src_id, dst_id, label=prop_id) for (src_id, dst_id, prop_id) in
        rels_set
    ]
    return {"nodes": nodes, "edges": rels}


class TuGraphStore(GraphStoreBase):
    """TuGraph graph store."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        pwd: str,
        graph_name: str,
        node_label: str = "entity",
        edge_label: str = "rel",
        **kwargs: Any,
    ) -> None:
        """Initialize the TuGraphStore with connection details."""
        self.conn = TuGraphConnector.from_uri_db(
            host=host, port=port, user=user, pwd=pwd, db_name=graph_name
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
        return result

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        del_query = (
            f"MATCH (n1:{self._node_label} {{id:'{sub}'}})"
            f"-[r:{self._edge_label} {{id:'{rel}'}}]->"
            f"(n2:{self._node_label} {{id:'{obj}'}}) DELETE n1,n2,r"
        )
        self.conn.run(query=del_query)

    def drop(self):
        # todo: drop graph
        pass

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
            result = self.conn.run(query=query)
            graph = _format_query_data(result)
            mg = MemoryGraph()
            for vertex in graph["nodes"]:
                mg.upsert_vertex(vertex)
            for edge in graph["edges"]:
                mg.append_edge(edge)
            return mg

    def query(self, query: str, **args) -> MemoryGraph:
        """Execute a query on graph."""
        result = self.conn.run(query=query)
        graph = _format_query_data(result)
        mg = MemoryGraph()
        for vertex in graph["nodes"]:
            mg.upsert_vertex(vertex)
        for edge in graph["edges"]:
            mg.append_edge(edge)
        return mg
