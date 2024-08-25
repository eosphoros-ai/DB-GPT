"""TuGraph store."""
import base64
import json
import logging
import os
from typing import Generator, Iterator, List, Optional, Tuple

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Direction, Edge, Graph, MemoryGraph, \
    Vertex

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
        default="73@TuGraph",
        description="login password",
    )
    vertex_type: str = Field(
        default="entity",
        description="The type of vertex, `entity` by default.",
    )
    edge_type: str = Field(
        default="relation",
        description="The type of edge, `relation` by default.",
    )
    plugin_names: List[str] = Field(
        default=["leiden"],
        description=(
            "Plugins need to be loaded when initialize TuGraph, "
            "code: https://github.com/TuGraph-family"
            "/dbgpt-tugraph-plugins/tree/master/cpp"
        )
    )


class TuGraphStore(GraphStoreBase):
    """TuGraph graph store."""

    def __init__(self, config: TuGraphStoreConfig) -> None:
        """Initialize the TuGraphStore with connection details."""
        self._config = config
        self._host = os.getenv("TUGRAPH_HOST", config.host)
        self._port = int(os.getenv("TUGRAPH_PORT", config.port))
        self._username = os.getenv("TUGRAPH_USERNAME", config.username)
        self._password = os.getenv("TUGRAPH_PASSWORD", config.password)
        self._summary_enabled = (
            os.getenv("GRAPH_COMMUNITY_SUMMARY_ENABLED", "").lower() == "true"
            or config.summary_enabled
        )
        self._plugin_names = (
            os.getenv("TUGRAPH_PLUGIN_NAMES", "leiden").split(",")
            or config.plugin_names
        )
        self._graph_name = config.name
        self._vertex_type = os.getenv("TUGRAPH_VERTEX_TYPE", config.vertex_type)
        self._edge_type = os.getenv("TUGRAPH_EDGE_TYPE", config.edge_type)

        self.conn = TuGraphConnector.from_uri_db(
            host=self._host,
            port=self._port,
            user=self._username,
            pwd=self._password,
            db_name=config.name,
        )

        self._create_graph(config.name)

    def get_vertex_type(self) -> str:
        """Get the vertex type."""
        return self._vertex_type

    def get_edge_type(self) -> str:
        """Get the edge type."""
        return self._edge_type

    def _create_graph(self, graph_name: str):
        self.conn.create_graph(graph_name=graph_name)
        self._create_schema()
        if self._summary_enabled:
            self._upload_plugin()

    def _check_label(self, elem_type: str):
        result = self.conn.get_table_names()
        if elem_type == "vertex":
            return self._vertex_type in result["vertex_tables"]
        if elem_type == "edge":
            return self._edge_type in result["edge_tables"]

    def _add_vertex_index(self, field_name):
        gql = f"CALL db.addIndex('{self._vertex_type}', '{field_name}', false)"
        self.conn.run(gql)

    def _upload_plugin(self):
        gql = f"CALL db.plugin.listPlugin('CPP','v1')"
        result = self.conn.run(gql)
        result_names = [
            json.loads(record["plugin_description"])["name"] for record in
            result
        ]
        missing_plugins = [
            name for name in self._plugin_names if name not in result_names
        ]

        if len(missing_plugins):
            for name in missing_plugins:
                from dbgpt_tugraph_plugins import get_plugin_binary_path

                plugin_path = get_plugin_binary_path("leiden")
                print(plugin_path)
                with open(plugin_path, "rb") as f:
                    content = f.read()
                content = base64.b64encode(content).decode()
                gql = f"CALL db.plugin.loadPlugin('CPP','{name}','{content}','SO','{name} Plugin',false,'v1')"
                self.conn.run(gql)

    def _create_schema(self):
        if not self._check_label("vertex"):
            if self._summary_enabled:
                create_vertex_gql = (
                    f"CALL db.createLabel("
                    f"'vertex', '{self._vertex_type}', "
                    f"'id', ['id',string,false],"
                    f"['name',string,false],"
                    f"['_document_id',string,true],"
                    f"['_chunk_id',string,true],"
                    f"['_community_id',string,true],"
                    f"['description',string,true])"
                )
                self.conn.run(create_vertex_gql)
                self._add_vertex_index("_community_id")
            else:
                create_vertex_gql = (
                    f"CALL db.createLabel("
                    f"'vertex', '{self._vertex_type}', "
                    f"'id', ['id',string,false],"
                    f"['name',string,false])"
                )
                self.conn.run(create_vertex_gql)

        if not self._check_label("edge"):
            create_edge_gql = f"""CALL db.createLabel(
                    'edge', '{self._edge_type}', '[["{self._vertex_type}",
                    "{self._vertex_type}"]]', ["id",STRING,false],["name",STRING,false])"""
            if self._summary_enabled:
                create_edge_gql = f"""CALL db.createLabel(
                    'edge', '{self._edge_type}', '[["{self._vertex_type}",
                    "{self._vertex_type}"]]', ["id",STRING,false],["name",STRING,false],["description",STRING,true])"""
            self.conn.run(create_edge_gql)

    def get_config(self):
        """Get the graph store config."""
        return self._config

    def get_triplets(self, subj: str) -> List[Tuple[str, str]]:
        """Get triplets."""
        query = (
            f"MATCH (n1:{self._vertex_type})-[r]->(n2:{self._vertex_type}) "
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

        node_query = f"CALL db.upsertVertex('{self._vertex_type}', [{{id:'{subj_escaped}',name:'{subj_escaped}'}},{{id:'{obj_escaped}',name:'{obj_escaped}'}}])"
        edge_query = f"""CALL db.upsertEdge('{self._edge_type}', {{type:"{self._vertex_type}", key:"sid"}}, {{type:"entity", key:"tid"}}, [{{sid:"{subj_escaped}", tid: "{obj_escaped}",id:"{rel_escaped}", name: "{rel_escaped}"}}])"""

        self.conn.run(query=node_query)
        self.conn.run(query=edge_query)

    def insert_graph(self, graph: Graph) -> None:
        """Add graph."""

        def escape_quotes(value: str) -> str:
            """Escape single and double quotes in a string for queries."""
            if value is not None:
                return value.replace("'", "").replace('"', "")

        nodes: Iterator[Vertex] = graph.vertices()
        edges: Iterator[Edge] = graph.edges()
        node_list = []
        edge_list = []

        def parser(node_list):
            return f"""{', '.join(['{' + ', '.join([f'{k}: "{v}"' if isinstance(v, str) else f'{k}: {v}' for k, v in node.items()]) + '}' for node in node_list])}"""

        for node in nodes:
            node_list.append(
                {
                    "id": escape_quotes(node.vid),
                    "name": escape_quotes(node.name),
                    "description": escape_quotes(
                        node.get_prop("description")) or "",
                    "_document_id": "0",
                    "_chunk_id": "0",
                    "_community_id": "0"
                }
            )
        node_query = (
            f"""CALL db.upsertVertex("{self._vertex_type}", [{parser(node_list)}])"""
        )
        for edge in edges:
            edge_list.append(
                {
                    "sid": escape_quotes(edge.sid),
                    "tid": escape_quotes(edge.tid),
                    "id": escape_quotes(edge.name),
                    "name": escape_quotes(edge.name),
                    "description": escape_quotes(edge.get_prop("description")),
                }
            )

        edge_query = f"""CALL db.upsertEdge("{self._edge_type}", {{type:"{self._vertex_type}", key:"sid"}}, {{type:"entity", key:"tid"}}, [{parser(edge_list)}])"""
        self.conn.run(query=node_query)
        self.conn.run(query=edge_query)

    def truncate(self):
        """Truncate Graph."""
        gql = 'MATCH (n) DELETE n'
        self.conn.run(gql)

    def drop(self):
        """Delete Graph."""
        self.conn.delete_graph(self._graph_name)

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        del_query = (
            f"MATCH (n1:{self._vertex_type} {{id:'{sub}'}})"
            f"-[r:{self._edge_type} {{id:'{rel}'}}]->"
            f"(n2:{self._vertex_type} {{id:'{obj}'}}) DELETE n1,n2,r"
        )
        self.conn.run(query=del_query)

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        query = "CALL dbms.graph.getGraphSchema()"
        data = self.conn.run(query=query)
        schema = data[0]["schema"]
        return schema

    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
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
    ) -> Graph:
        if not subs:
            return MemoryGraph()

        """Explore the graph from given subjects up to a depth."""
        if fan is not None:
            raise ValueError("Fan functionality is not supported at this time.")
        else:
            depth_string = f"1..{depth}"
            if depth is None:
                depth_string = ".."

            limit_string = f"LIMIT {limit}"
            print(direct.name)
            if limit is None:
                limit_string = ""
            if direct.name == "OUT":
                rel = f"-[r:{self._edge_type}*{depth_string}]->"
            elif direct.name == "IN":
                rel = f"<-[r:{self._edge_type}*{depth_string}]-"
            else:
                rel = f"-[r:{self._edge_type}*{depth_string}]-"
            query = (
                f"MATCH p=(n:{self._vertex_type})"
                f"{rel}(m:{self._vertex_type}) "
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
                    formatted_path.append(
                        {
                            "id": nodes[i]._properties["id"],
                            "community_id": nodes[i]._properties.get(
                                "_community_id", ""
                            ),
                            "description": nodes[i]._properties.get(
                                "description", ""),
                        }
                    )
                    if i < len(rels):
                        formatted_path.append(
                            {
                                "id": rels[i]._properties["id"],
                                "description": rels[i]._properties.get(
                                    "description", ""
                                ),
                            }
                        )
                formatted_paths.append(formatted_path)
            return formatted_paths

        def _format_query_data(data):
            nodes_list = []
            rels_list = []
            from neo4j import graph

            for record in data:
                for key in record.keys():
                    value = record[key]
                    if isinstance(value, graph.Node):
                        node_id = value._properties["id"]
                        description = value._properties.get("description", "")
                        community_id = value._properties.get("community_id", "")
                        if not any(
                            existing_node.get("id") == node_id
                            for existing_node in nodes_list
                        ):
                            nodes_list.append(
                                {"id": node_id, "description": description}
                            )
                    elif isinstance(value, graph.Relationship):
                        rel_nodes = value.nodes
                        prop_id = value._properties["id"]
                        src_id = rel_nodes[0]._properties["id"]
                        dst_id = rel_nodes[1]._properties["id"]
                        description = value._properties.get("description", "")
                        if not any(
                            existing_edge.get("prop_id") == prop_id
                            and existing_edge.get("src_id") == src_id
                            and existing_edge.get("dst_id") == dst_id
                            for existing_edge in rels_list
                        ):
                            rels_list.append(
                                {
                                    "src_id": src_id,
                                    "dst_id": dst_id,
                                    "prop_id": prop_id,
                                    "description": description,
                                }
                            )
                    elif isinstance(value, graph.Path):
                        formatted_paths = _format_paths(data)
                        for formatted_path in formatted_paths:

                            for i in range(0, len(formatted_path), 2):
                                if not any(
                                    existing_node.get("id") ==
                                    formatted_path[i]["id"]
                                    for existing_node in nodes_list
                                ):
                                    nodes_list.append(
                                        {
                                            "id": formatted_path[i]["id"],
                                            "description": formatted_path[i][
                                                "description"
                                            ],
                                        }
                                    )
                                if i + 2 < len(formatted_path):
                                    src_id = formatted_path[i]["id"]
                                    dst_id = formatted_path[i + 2]["id"]
                                    prop_id = formatted_path[i + 1]["id"]
                                    if not any(
                                        existing_edge.get("prop_id") == prop_id
                                        and existing_edge.get(
                                            "src_id") == src_id
                                        and existing_edge.get(
                                            "dst_id") == dst_id
                                        for existing_edge in rels_list
                                    ):
                                        rels_list.append(
                                            {
                                                "src_id": src_id,
                                                "dst_id": dst_id,
                                                "prop_id": prop_id,
                                                "description":
                                                    formatted_path[i + 1][
                                                        "description"
                                                    ],
                                            }
                                        )
                    else:
                        if not any(
                            existing_node.get("id") == node_id
                            for existing_node in nodes_list
                        ):
                            nodes_list.append(
                                {"id": "json_node", "description": value})

            nodes = [
                Vertex(node["id"], description=node["description"])
                for node in nodes_list
            ]
            rels = [
                Edge(
                    edge["src_id"],
                    edge["dst_id"],
                    label=edge["prop_id"],
                    description=edge["description"],
                )
                for edge in rels_list
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

    def stream_query(self, query: str) -> Generator[Graph, None, None]:
        """Execute a stream query."""
        from neo4j import graph

        for record in self.conn.run_stream(query):
            mg = MemoryGraph()
            for key in record.keys():
                value = record[key]
                if isinstance(value, graph.Node):
                    node_id = value._properties["id"]
                    description = value._properties["description"]
                    vertex = Vertex(node_id, description=description)
                    mg.upsert_vertex(vertex)
                elif isinstance(value, graph.Relationship):
                    rel_nodes = value.nodes
                    prop_id = value._properties["id"]
                    src_id = rel_nodes[0]._properties["id"]
                    dst_id = rel_nodes[1]._properties["id"]
                    description = value._properties["description"]
                    edge = Edge(src_id, dst_id, label=prop_id,
                                description=description)
                    mg.append_edge(edge)
                elif isinstance(value, graph.Path):
                    nodes = list(record["p"].nodes)
                    rels = list(record["p"].relationships)
                    formatted_path = []
                    for i in range(len(nodes)):
                        formatted_path.append(
                            {
                                "id": nodes[i]._properties["id"],
                                "description": nodes[i]._properties[
                                    "description"],
                            }
                        )
                        if i < len(rels):
                            formatted_path.append(
                                {
                                    "id": rels[i]._properties["id"],
                                    "description": rels[i]._properties[
                                        "description"],
                                }
                            )
                    for i in range(0, len(formatted_path), 2):
                        mg.upsert_vertex(
                            Vertex(
                                formatted_path[i]["id"],
                                description=formatted_path[i]["description"],
                            )
                        )
                        if i + 2 < len(formatted_path):
                            mg.append_edge(
                                Edge(
                                    formatted_path[i]["id"],
                                    formatted_path[i + 2]["id"],
                                    label=formatted_path[i + 1]["id"],
                                    description=formatted_path[i + 1][
                                        "description"],
                                )
                            )
                else:
                    vertex = Vertex("json_node", description=value)
                    mg.upsert_vertex(vertex)
            yield mg
