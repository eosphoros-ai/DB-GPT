"""TuGraph vector store."""
import logging
import os
from typing import List, Optional, Tuple

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Direction, Edge, MemoryGraph, Vertex

logger = logging.getLogger(__name__)


class TuGraphStoreConfig(GraphStoreConfig):
    """TuGraph store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    host: str = Field(
        default="127.0.0.1",
        description="TuGraph host",
    )
    port: int = Field(
        default=7687,
        description="TuGraph port",
    )
    username: str = Field(
        default="admin",
        description="login username",
    )
    password: str = Field(
        default="123456",
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


class TuGraphStore(GraphStoreBase):
    """TuGraph graph store."""

    def __init__(self, config: TuGraphStoreConfig) -> None:
        """Initialize the TuGraphStore with connection details."""
        self._host = os.getenv("TUGRAPH_HOST", "127.0.0.1") or config.host
        self._port = int(os.getenv("TUGRAPH_PORT", 7687)) or config.port
        self._username = os.getenv("TUGRAPH_USERNAME", "admin") or config.username
        self._password = os.getenv("TUGRAPH_PASSWORD", "73@TuGraph") or config.password
        self._node_label = (
            os.getenv("TUGRAPH_VERTEX_TYPE", "entity") or config.vertex_type
        )
        self._edge_label = (
            os.getenv("TUGRAPH_EDGE_TYPE", "relation") or config.edge_type
        )
        self.edge_name_key = (
            os.getenv("TUGRAPH_EDGE_NAME_KEY", "label") or config.edge_name_key
        )
        self._graph_name = config.name
        self.conn = TuGraphConnector.from_uri_db(
            host=self._host,
            port=self._port,
            user=self._username,
            pwd=self._password,
            db_name=config.name,
        )
        self.conn.create_graph(graph_name=config.name)

        self._create_schema()

    def _check_label(self, elem_type: str):
        result = self.conn.get_table_names()
        if elem_type == "vertex":
            return self._node_label in result["vertex_tables"]
        if elem_type == "edge":
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

        def escape_quotes(value: str) -> str:
            """Escape single and double quotes in a string for queries."""
            return value.replace("'", "\\'").replace('"', '\\"')

        subj_escaped = escape_quotes(subj)
        rel_escaped = escape_quotes(rel)
        obj_escaped = escape_quotes(obj)

        subj_query = f"MERGE (n1:{self._node_label} {{id:'{subj_escaped}'}})"
        obj_query = f"MERGE (n1:{self._node_label} {{id:'{obj_escaped}'}})"
        rel_query = (
            f"MERGE (n1:{self._node_label} {{id:'{subj_escaped}'}})"
            f"-[r:{self._edge_label} {{id:'{rel_escaped}'}}]->"
            f"(n2:{self._node_label} {{id:'{obj_escaped}'}})"
        )
        self.conn.run(query=subj_query)
        self.conn.run(query=obj_query)
        self.conn.run(query=rel_query)

    def drop(self):
        """Delete Graph."""
        self.conn.delete_graph(self._graph_name)

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

    def get_full_graph(self, limit: Optional[int] = None) -> MemoryGraph:
        """Get full graph."""
        if not limit:
            raise Exception("limit must be set")
        return self.query(f"MATCH (n)-[r]-(m) RETURN n,m,r LIMIT {limit}")

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: Optional[int] = None,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if fan is not None:
            raise ValueError("Fan functionality is not supported at this time.")
        else:
            depth_string = f"1..{depth}"
            if depth is None:
                depth_string = ".."

            limit_string = f"LIMIT {limit}"
            if limit is None:
                limit_string = ""

            query = (
                f"MATCH p=(n:{self._node_label})"
                f"-[r:{self._edge_label}*{depth_string}]-(m:{self._node_label}) "
                f"WHERE n.id IN {subs} RETURN p {limit_string}"
            )
            return self.query(query)

    def query(self, query: str, **args) -> MemoryGraph:
        """Execute a query on graph."""

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
                Edge(src_id, dst_id, label=prop_id)
                for (src_id, dst_id, prop_id) in rels_set
            ]
            return {"nodes": nodes, "edges": rels}

        result = self.conn.run(query=query)
        graph = _format_query_data(result)
        mg = MemoryGraph()
        for vertex in graph["nodes"]:
            mg.upsert_vertex(vertex)
        for edge in graph["edges"]:
            mg.append_edge(edge)
        return mg
