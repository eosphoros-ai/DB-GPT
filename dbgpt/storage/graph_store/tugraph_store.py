"""TuGraph store."""

import base64
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Tuple

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Edge, Graph, GraphElemType, MemoryGraph, Vertex

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
        default=GraphElemType.ENTITY.value,
        description="The type of entity vertex, `entity` by default.",
    )
    document_type: str = Field(
        default=GraphElemType.DOCUMENT.value,
        description="The type of document vertex, `document` by default.",
    )
    chunk_type: str = Field(
        default=GraphElemType.CHUNK.value,
        description="The type of chunk vertex, `relation` by default.",
    )
    edge_type: str = Field(
        default=GraphElemType.RELATION.value,
        description="The type of relation edge, `relation` by default.",
    )
    include_type: str = Field(
        default=GraphElemType.INCLUDE.value,
        description="The type of include edge, `include` by default.",
    )
    next_type: str = Field(
        default=GraphElemType.NEXT.value,
        description="The type of next edge, `next` by default.",
    )
    plugin_names: List[str] = Field(
        default=["leiden"],
        description=(
            "Plugins need to be loaded when initialize TuGraph, "
            "code: https://github.com/TuGraph-family"
            "/dbgpt-tugraph-plugins/tree/master/cpp"
        ),
    )


class TuGraphStore(GraphStoreBase):
    """TuGraph graph store."""

    def __init__(self, config: TuGraphStoreConfig) -> None:
        """Initialize the TuGraphStore with connection details."""
        self._config = config
        # TODO: Rememmber to config the config object while initializing the class.
        # TODO: Do we need to use kwargs in the constructor?
        self._host = config.host
        self._port = config.port
        self._username = config.username
        self._password = config.password
        self._summary_enabled = config.summary_enabled  # summary the community in the graph
        self._plugin_names = config.plugin_names

        self._graph_name = config.name

        self.conn = TuGraphConnector.from_uri_db(
            host=self._host,
            port=self._port,
            user=self._username,
            pwd=self._password,
            db_name=config.name,
        )

        # self._create_graph(config.name)

    def get_config(self) -> TuGraphStoreConfig:
        """Get the TuGraph store config."""
        return self._config

    def _add_vertex_index(self, field_name):
        """Add an index to the vertex table."""
        gql = f"CALL db.addIndex('{GraphElemType.ENTITY.value}', '{field_name}', false)"
        self.conn.run(gql)

    def _upload_plugin(self):
        """Upload missing plugins to the TuGraph database.

        This method checks for the presence of required plugins in the database and uploads any missing plugins.
        It performs the following steps:
        1. Lists existing plugins in the database.
        2. Identifies missing plugins by comparing with the required plugin list.
        3. For each missing plugin, reads its binary content, encodes it, and uploads to the database.

        The method uses the 'leiden' plugin as an example, but can be extended for other plugins.
        """
        gql = "CALL db.plugin.listPlugin('CPP','v1')"
        result = self.conn.run(gql)
        result_names = [json.loads(record["plugin_description"])["name"] for record in result]
        missing_plugins = [name for name in self._plugin_names if name not in result_names]

        if len(missing_plugins):
            for name in missing_plugins:
                try:
                    from dbgpt_tugraph_plugins import get_plugin_binary_path
                except ImportError:
                    logger.error(
                        "dbgpt-tugraph-plugins is not installed, "
                        "pip install dbgpt-tugraph-plugins==0.1.0rc1 -U -i "
                        "https://pypi.org/simple"
                    )
                plugin_path = get_plugin_binary_path("leiden")
                with open(plugin_path, "rb") as f:
                    content = f.read()
                content = base64.b64encode(content).decode()
                gql = f"CALL db.plugin.loadPlugin('CPP', '{name}', '{content}', 'SO', '{name} Plugin', false, 'v1')"
                self.conn.run(gql)

    def get_nodes_edges_from_queried_data(
        self,
        data: List[Dict[str, Any]],
        white_prop_list: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Format the query data.

        Args:
            data: The data to be formatted.
            white_prop_list: The white list of properties.

        Returns:
            The formatted data.
        """
        nodes_list: List[Dict[str, Any]] = []
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        edges_list: List[Dict[str, Any]] = []
        edges_dict: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        _white_list = white_prop_list
        from neo4j import graph

        def filter_properties(properties: dict[str, Any], white_list: List[str]) -> Dict[str, Any]:
            """Filter the properties. It will remove the properties that are not in the white list.

            The expected propertities are:
                entity_properties = ["id", "name", "description", "_document_id", "_chunk_id", "_community_id"]
                edge_properties = ["id", "name", "description", "_chunk_id"]
            """
            return {
                key: value
                for key, value in properties.items()
                if (not key.startswith("_") and key not in ["id", "name"]) or key in white_list
            }

        def add_node(node_data: Dict[str, Any]):
            """Add a node to the nodes dictionary if it doesn't exist."""
            node_id = node_data.get("id")
            if node_id not in nodes_dict:
                nodes_dict[node_id] = node_data
                nodes_list.append(node_data)

        def add_edge(edge_data: Dict[str, Any]):
            """Add an edge to the edges dictionary if it doesn't exist."""
            edge_key = (edge_data.get("src_id"), edge_data.get("dst_id"), edge_data.get("name"))
            if edge_key not in edges_dict:
                edges_dict[edge_key] = edge_data
                edges_list.append(edge_data)

        for record in data:
            for value in record.values():
                if isinstance(value, graph.Node):
                    node_data = {
                        "id": value._properties.get("id"),
                        "name": value._properties.get("name"),
                        "type": next(iter(value._labels)),
                        "properties": filter_properties(value._properties, _white_list),
                    }
                    add_node(node_data)
                elif isinstance(value, graph.Relationship):
                    for node in value.nodes:  # num of nodes is 2
                        node_data = {
                            "id": node._properties.get("id"),
                            "name": node._properties.get("name"),
                            "type": next(iter(node._labels)),
                            "properties": filter_properties(node._properties, _white_list),
                        }
                        add_node(node_data)

                        edge_data = {
                            "src_id": value.nodes[0]._properties.get("id"),
                            "dst_id": value.nodes[1]._properties.get("id"),
                            "name": value._properties.get("name"),
                            "type": value.type,
                            "properties": filter_properties(value._properties, _white_list),
                        }
                        add_edge(edge_data)
                elif isinstance(value, graph.Path):
                    for edge in value.relationships:
                        for node in edge.nodes:
                            node_data = {
                                "id": node._properties.get("id"),
                                "name": node._properties.get("name"),
                                "type": next(iter(node._labels)),
                                "properties": filter_properties(node._properties, _white_list),
                            }
                            add_node(node_data)

                            edge_data = {
                                "src_id": edge.nodes[0]._properties.get("id"),
                                "dst_id": edge.nodes[1]._properties.get("id"),
                                "name": edge._properties.get("name"),
                                "type": edge.type,
                                "properties": filter_properties(edge._properties, _white_list),
                            }
                            add_edge(edge_data)
                else:  # json_node
                    node_data = {
                        "id": "json_node",
                        "name": "json_node",
                        "type": "json_node",
                        "properties": {"description": value},
                    }
                    add_node(node_data)

        return nodes_list, edges_list

    def _escape_quotes(self, value: str) -> str:
        """Escape single and double quotes in a string for queries."""
        if value is not None:
            return value.replace("'", "").replace('"', "")

    def _parser(self, entity_list):
        formatted_nodes = [
            "{" + ", ".join(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}" for k, v in node.items()) + "}"
            for node in entity_list
        ]
        return f"""{", ".join(formatted_nodes)}"""

    def _upsert_chunk_include_chunk(self, edges):
        pass
        # TODO: To be removed to the adapter class.

    def _upsert_chunk_include_entity(self, edges):
        pass
        # TODO: To be removed to the adapter class.

    def query(self, query: str, **kwargs) -> MemoryGraph:
        """Execute a query on graph.

        white_list: List[str] = kwargs.get("white_list", []), which contains the white list of properties
        and filters the properties that are not in the white list.
        """
        query_result = self.conn.run(query=query)
        white_list: List[str] = kwargs.get(
            "white_list",
            [
                "id",
                "name",
                "description",
                "_document_id",
                "_chunk_id",
                "_community_id",
            ],
        )
        nodes, edges = self.get_nodes_edges_from_queried_data(query_result, white_list)
        mg = MemoryGraph()
        for vertex in nodes:
            mg.upsert_vertex(vertex)
        for edge in edges:
            mg.append_edge(edge)
        return mg

    async def stream_query(self, query: str, **kwargs) -> AsyncGenerator[Graph, None]:
        """Execute a stream query."""
        from neo4j import graph

        async for record in self.conn.run_stream(query):
            mg = MemoryGraph()
            for key in record.keys():
                value = record[key]
                if isinstance(value, graph.Node):
                    node_id = value._properties["id"]
                    description = value._properties["description"]
                    vertex = Vertex(node_id, name=node_id, description=description)
                    mg.upsert_vertex(vertex)
                elif isinstance(value, graph.Relationship):
                    edge_nodes = value.nodes
                    prop_id = value._properties["id"]
                    src_id = edge_nodes[0]._properties["id"]
                    dst_id = edge_nodes[1]._properties["id"]
                    description = value._properties["description"]
                    edge = Edge(src_id, dst_id, name=prop_id, description=description)
                    mg.append_edge(edge)
                elif isinstance(value, graph.Path):
                    nodes = list(record["p"].nodes)
                    rels = list(record["p"].relationships)
                    formatted_path = []
                    for i in range(len(nodes)):
                        formatted_path.append({
                            "id": nodes[i]._properties["id"],
                            "description": nodes[i]._properties["description"],
                        })
                        if i < len(rels):
                            formatted_path.append({
                                "id": rels[i]._properties["id"],
                                "description": rels[i]._properties["description"],
                            })
                    for i in range(0, len(formatted_path), 2):
                        mg.upsert_vertex(
                            Vertex(
                                formatted_path[i]["id"],
                                name=formatted_path[i]["id"],
                                description=formatted_path[i]["description"],
                            )
                        )
                        if i + 2 < len(formatted_path):
                            mg.append_edge(
                                Edge(
                                    formatted_path[i]["id"],
                                    formatted_path[i + 2]["id"],
                                    name=formatted_path[i + 1]["id"],
                                    description=formatted_path[i + 1]["description"],
                                )
                            )
                else:
                    vertex = Vertex("json_node", name="json_node", description=value)
                    mg.upsert_vertex(vertex)
            yield mg
