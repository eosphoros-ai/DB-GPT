"""TuGraph Community Store Adapter."""

import json
import logging
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
)

from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)
from dbgpt.storage.graph_store.tugraph_store import TuGraphStore
from dbgpt.storage.knowledge_graph.base import ParagraphChunk
from dbgpt.storage.knowledge_graph.community.base import Community, GraphStoreAdapter

logger = logging.getLogger(__name__)


class TuGraphStoreAdapter(GraphStoreAdapter):
    """TuGraph Community Store Adapter."""

    MAX_QUERY_LIMIT = 1000
    MAX_HIERARCHY_LEVEL = 3

    def __init__(self, graph_store: TuGraphStore):
        """Initialize TuGraph Community Store Adapter."""
        super().__init__(graph_store)

        # Create the graph
        self.create_graph(self.graph_store.get_config().name)

    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery with leiden."""
        mg = self.query(
            "CALL db.plugin.callPlugin('CPP',"
            "'leiden','{\"leiden_val\":\"_community_id\"}',60.00,false)"
        )
        result = mg.get_vertex("json_node").get_prop("description")
        community_ids = json.loads(result)["community_id_list"]
        logger.info(f"Discovered {len(community_ids)} communities.")
        return community_ids

    async def get_community(self, community_id: str) -> Community:
        """Get community."""
        query = (
            f"MATCH (n:{self.get_vertex_type()}) WHERE n._community_id = "
            f"'{community_id}' RETURN n"
        )
        edge_query = (
            f"MATCH (n:{self.get_vertex_type()})-"
            f"[r:{self.get_edge_type()}]-"
            f"(m:{self.get_vertex_type()})"
            f"WHERE n._community_id = '{community_id}' RETURN n,r,m"
        )

        all_vertex_graph = self.query(query)
        all_edge_graph = self.query(edge_query)
        all_graph = MemoryGraph()
        for vertex in all_vertex_graph.vertices():
            all_graph.upsert_vertex(vertex)
        for edge in all_edge_graph.edges():
            all_graph.append_edge(edge)

        return Community(id=community_id, data=all_graph)

    @property
    def graph_store(self) -> TuGraphStore:
        """Get the graph store."""
        return self._graph_store  # type: ignore[return-value]

    def get_graph_config(self):
        """Get the graph store config."""
        return self.graph_store.get_config()

    def get_vertex_type(self) -> str:
        """Get the vertex type."""
        return GraphElemType.ENTITY.value

    def get_edge_type(self) -> str:
        """Get the edge type."""
        return GraphElemType.RELATION.value

    def get_triplets(self, subj: str) -> List[Tuple[str, str]]:
        """Get triplets."""
        triplet_query = (
            f"MATCH (n1:{GraphElemType.ENTITY.value})-[r]->(n2:"
            f"{GraphElemType.ENTITY.value}) "
            f'WHERE n1.id = "{subj}" RETURN r.id as rel, n2.id as obj;'
        )
        data = self.graph_store.conn.run(triplet_query)
        return [(record["rel"], record["obj"]) for record in data]

    def get_document_vertex(self, doc_name: str) -> Vertex:
        """Get the document vertex in the graph."""
        gql = f"""MATCH (n) WHERE n.id = {doc_name} RETURN n"""
        graph = self.query(gql)
        vertex = graph.get_vertex(doc_name)
        return vertex

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        query = "CALL dbms.graph.getGraphSchema()"
        data = self.graph_store.conn.run(query=query)
        schema = data[0]["schema"]
        return schema

    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Get full graph."""
        if not limit:
            limit = self.MAX_QUERY_LIMIT
        if limit <= 0:
            raise ValueError("Limit must be greater than 0.")
        graph_result = self.query(
            f"MATCH (n)-[r]-(m) RETURN n,r,m LIMIT {limit}",
            white_list=["_community_id"],
        )
        full_graph = MemoryGraph()
        for vertex in graph_result.vertices():
            full_graph.upsert_vertex(vertex)
        for edge in graph_result.edges():
            full_graph.append_edge(edge)
        return full_graph

    def upsert_entities(self, entities: Iterator[Vertex]) -> None:
        """Upsert entities."""
        entity_list = [
            {
                "id": self._escape_quotes(entity.vid),
                "name": self._escape_quotes(entity.name),
                "description": self._escape_quotes(entity.get_prop("description"))
                or "",
                "_document_id": "0",
                "_chunk_id": "0",
                "_community_id": "0",
            }
            for entity in entities
        ]
        entity_query = (
            f"CALL db.upsertVertex("
            f'"{GraphElemType.ENTITY.value}", '
            f"[{self._convert_dict_to_str(entity_list)}])"
        )
        self.graph_store.conn.run(query=entity_query)

    def upsert_edge(
        self, edges: Iterator[Edge], edge_type: str, src_type: str, dst_type: str
    ) -> None:
        """Upsert edges."""
        edge_list = [
            {
                "sid": self._escape_quotes(edge.sid),
                "tid": self._escape_quotes(edge.tid),
                "id": self._escape_quotes(edge.name),
                "name": self._escape_quotes(edge.name),
                "description": self._escape_quotes(edge.get_prop("description")) or "",
                "_chunk_id": self._escape_quotes(edge.get_prop("_chunk_id")) or "",
            }
            for edge in edges
        ]
        relation_query = f"""CALL db.upsertEdge("{edge_type}",
            {{type:"{src_type}", key:"sid"}},
            {{type:"{dst_type}", key:"tid"}},
            [{self._convert_dict_to_str(edge_list)}])"""
        self.graph_store.conn.run(query=relation_query)

    def upsert_chunks(self, chunks: Iterator[Union[Vertex, ParagraphChunk]]) -> None:
        """Upsert chunks."""
        chunk_list = [
            {
                "id": self._escape_quotes(chunk.chunk_id),
                "name": self._escape_quotes(chunk.chunk_name),
                "content": self._escape_quotes(chunk.content),
            }
            if isinstance(chunk, ParagraphChunk)
            else {
                "id": self._escape_quotes(chunk.vid),
                "name": self._escape_quotes(chunk.name),
                "content": self._escape_quotes(chunk.get_prop("content")),
            }
            for chunk in chunks
        ]

        chunk_query = (
            f"CALL db.upsertVertex("
            f'"{GraphElemType.CHUNK.value}", '
            f"[{self._convert_dict_to_str(chunk_list)}])"
        )
        self.graph_store.conn.run(query=chunk_query)

    def upsert_documents(
        self, documents: Iterator[Union[Vertex, ParagraphChunk]]
    ) -> None:
        """Upsert documents."""
        document_list = [
            {
                "id": self._escape_quotes(document.chunk_id),
                "name": self._escape_quotes(document.chunk_name),
                "content": "",
            }
            if isinstance(document, ParagraphChunk)
            else {
                "id": self._escape_quotes(document.vid),
                "name": self._escape_quotes(document.name),
                "content": "",
            }
            for document in documents
        ]

        document_query = (
            "CALL db.upsertVertex("
            f'"{GraphElemType.DOCUMENT.value}", '
            f"[{self._convert_dict_to_str(document_list)}])"
        )
        self.graph_store.conn.run(query=document_query)

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        subj_escaped = subj.replace("'", "\\'").replace('"', '\\"')
        rel_escaped = rel.replace("'", "\\'").replace('"', '\\"')
        obj_escaped = obj.replace("'", "\\'").replace('"', '\\"')

        vertex_query = f"""CALL db.upsertVertex(
            '{GraphElemType.ENTITY.value}',
            [{{id:'{subj_escaped}',name:'{subj_escaped}'}},
            {{id:'{obj_escaped}',name:'{obj_escaped}'}}])"""
        edge_query = f"""CALL db.upsertEdge(
            '{GraphElemType.RELATION.value}',
            {{type:"{GraphElemType.ENTITY.value}",key:"sid"}},
            {{type:"{GraphElemType.ENTITY.value}", key:"tid"}},
            [{{sid:"{subj_escaped}",
            tid: "{obj_escaped}",
            id:"{rel_escaped}",
            name: "{rel_escaped}"}}])"""

        self.graph_store.conn.run(query=vertex_query)
        self.graph_store.conn.run(query=edge_query)

    def upsert_graph(self, graph: Graph) -> None:
        """Add graph to the graph store.

        Args:
            graph (Graph): The graph to be added.
        """
        # Get the iterators of all the vertices and the edges from the graph
        documents: Iterator[Vertex] = graph.vertices(
            filter_fn=lambda x: x.get_prop("vertex_type")
            == GraphElemType.DOCUMENT.value
        )
        chunks: Iterator[Vertex] = graph.vertices(
            filter_fn=lambda x: x.get_prop("vertex_type") == GraphElemType.CHUNK.value
        )
        entities: Iterator[Vertex] = graph.vertices(
            filter_fn=lambda x: x.get_prop("vertex_type") == GraphElemType.ENTITY.value
        )
        doc_include_chunk: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.get_prop("edge_type")
            == GraphElemType.DOCUMENT_INCLUDE_CHUNK.value
        )
        chunk_include_chunk: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.get_prop("edge_type")
            == GraphElemType.CHUNK_INCLUDE_CHUNK.value
        )
        chunk_include_entity: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.get_prop("edge_type")
            == GraphElemType.CHUNK_INCLUDE_ENTITY.value
        )
        chunk_next_chunk: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.get_prop("edge_type")
            == GraphElemType.CHUNK_NEXT_CHUNK.value
        )
        relation: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.get_prop("edge_type") == GraphElemType.RELATION.value
        )

        # Upsert the vertices and the edges to the graph store
        self.upsert_entities(entities)
        self.upsert_chunks(chunks)
        self.upsert_documents(documents)
        self.upsert_edge(
            doc_include_chunk,
            GraphElemType.INCLUDE.value,
            GraphElemType.DOCUMENT.value,
            GraphElemType.CHUNK.value,
        )
        self.upsert_edge(
            chunk_include_chunk,
            GraphElemType.INCLUDE.value,
            GraphElemType.CHUNK.value,
            GraphElemType.CHUNK.value,
        )
        self.upsert_edge(
            chunk_include_entity,
            GraphElemType.INCLUDE.value,
            GraphElemType.CHUNK.value,
            GraphElemType.ENTITY.value,
        )
        self.upsert_edge(
            chunk_next_chunk,
            GraphElemType.NEXT.value,
            GraphElemType.CHUNK.value,
            GraphElemType.CHUNK.value,
        )
        self.upsert_edge(
            relation,
            GraphElemType.RELATION.value,
            GraphElemType.ENTITY.value,
            GraphElemType.ENTITY.value,
        )

    def delete_document(self, chunk_ids: str) -> None:
        """Delete document in the graph."""
        chunkids_list = [uuid.strip() for uuid in chunk_ids.split(",")]
        del_chunk_gql = (
            f"MATCH(m:{GraphElemType.DOCUMENT.value})-[r]->"
            f"(n:{GraphElemType.CHUNK.value}) WHERE n.id IN {chunkids_list} DELETE n"
        )
        del_relation_gql = (
            f"MATCH(m:{GraphElemType.ENTITY.value})-[r:"
            f"{GraphElemType.RELATION.value}]-(n:{GraphElemType.ENTITY.value}) "
            f"WHERE r._chunk_id IN {chunkids_list} DELETE r"
        )
        delete_only_vertex = "MATCH (n) WHERE NOT EXISTS((n)-[]-()) DELETE n"
        self.graph_store.conn.run(del_chunk_gql)
        self.graph_store.conn.run(del_relation_gql)
        self.graph_store.conn.run(delete_only_vertex)

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        del_query = (
            f"MATCH (n1:{GraphElemType.ENTITY.value} {{id:'{sub}'}})"
            f"-[r:{GraphElemType.RELATION.value} {{id:'{rel}'}}]->"
            f"(n2:{GraphElemType.ENTITY.value} {{id:'{obj}'}}) DELETE n1,n2,r"
        )
        self.graph_store.conn.run(query=del_query)

    def drop(self):
        """Delete Graph."""
        self.graph_store.conn.delete_graph(self.get_graph_config().name)

    def create_graph(self, graph_name: str):
        """Create a graph."""
        if not self.graph_store.conn.create_graph(graph_name=graph_name):
            return

        # Create the graph schema
        def _format_graph_propertity_schema(
            name: str,
            type: str = "STRING",
            optional: bool = False,
            index: Optional[bool] = None,
            **kwargs,
        ) -> Dict[str, str | bool]:
            """Format the property for TuGraph.

            Args:
                name: The name of the property.
                type: The type of the property.
                optional: The optional of the property.
                index: The index of the property.
                kwargs: Additional keyword arguments.

            Returns:
                The formatted property.
            """
            property: Dict[str, str | bool] = {
                "name": name,
                "type": type,
                "optional": optional,
            }

            if index is not None:
                property["index"] = index

            # Add any additional keyword arguments to the property dictionary
            property.update(kwargs)
            return property

        # Create the graph label for document vertex
        document_proerties: List[Dict[str, Union[str, bool]]] = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_community_id", "STRING", True, True),
        ]
        self.create_graph_label(
            graph_elem_type=GraphElemType.DOCUMENT, graph_properties=document_proerties
        )

        # Create the graph label for chunk vertex
        chunk_proerties: List[Dict[str, Union[str, bool]]] = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_community_id", "STRING", True, True),
            _format_graph_propertity_schema("content", "STRING", True, True),
        ]
        self.create_graph_label(
            graph_elem_type=GraphElemType.CHUNK, graph_properties=chunk_proerties
        )

        # Create the graph label for entity vertex
        vertex_proerties: List[Dict[str, Union[str, bool]]] = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_community_id", "STRING", True, True),
            _format_graph_propertity_schema("description", "STRING", True, True),
        ]
        self.create_graph_label(
            graph_elem_type=GraphElemType.ENTITY, graph_properties=vertex_proerties
        )

        # Create the graph label for relation edge
        edge_proerties: List[Dict[str, Union[str, bool]]] = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_chunk_id", "STRING", True, True),
            _format_graph_propertity_schema("description", "STRING", True, True),
        ]
        self.create_graph_label(
            graph_elem_type=GraphElemType.RELATION, graph_properties=edge_proerties
        )

        # Create the graph label for include edge
        include_proerties: List[Dict[str, Union[str, bool]]] = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("description", "STRING", True),
        ]
        self.create_graph_label(
            graph_elem_type=GraphElemType.INCLUDE, graph_properties=include_proerties
        )

        # Create the graph label for next edge
        next_proerties: List[Dict[str, Union[str, bool]]] = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("description", "STRING", True),
        ]
        self.create_graph_label(
            graph_elem_type=GraphElemType.NEXT, graph_properties=next_proerties
        )

        if self.graph_store._enable_summary:
            self.graph_store._upload_plugin()

    def create_graph_label(
        self,
        graph_elem_type: GraphElemType,
        graph_properties: List[Dict[str, Union[str, bool]]],
    ) -> None:
        """Create a graph label.

        The graph label is used to identify and distinguish different types of nodes
        (vertices) and edges in the graph.
        """
        if graph_elem_type.is_vertex():  # vertex
            data = json.dumps(
                {
                    "label": graph_elem_type.value,
                    "type": "VERTEX",
                    "primary": "id",
                    "properties": graph_properties,
                }
            )
            gql = f"""CALL db.createVertexLabelByJson('{data}')"""
        else:  # edge

            def edge_direction(graph_elem_type: GraphElemType) -> List[List[str]]:
                """Define the edge direction.

                `include` edge: document -> chunk, chunk -> entity
                `next` edge: chunk -> chunk
                `relation` edge: entity -> entity
                """
                if graph_elem_type.is_vertex():
                    raise ValueError("The graph element type must be an edge.")
                if graph_elem_type == GraphElemType.INCLUDE:
                    return [
                        [GraphElemType.DOCUMENT.value, GraphElemType.CHUNK.value],
                        [GraphElemType.CHUNK.value, GraphElemType.ENTITY.value],
                        [GraphElemType.CHUNK.value, GraphElemType.CHUNK.value],
                    ]
                elif graph_elem_type == GraphElemType.NEXT:
                    return [[GraphElemType.CHUNK.value, GraphElemType.CHUNK.value]]
                elif graph_elem_type == GraphElemType.RELATION:
                    return [[GraphElemType.ENTITY.value, GraphElemType.ENTITY.value]]
                else:
                    raise ValueError("Invalid graph element type.")

            data = json.dumps(
                {
                    "label": graph_elem_type.value,
                    "type": "EDGE",
                    "constraints": edge_direction(graph_elem_type),
                    "properties": graph_properties,
                }
            )
            gql = f"""CALL db.createEdgeLabelByJson('{data}')"""

        self.graph_store.conn.run(gql)

    def truncate(self):
        """Truncate Graph."""
        gql = "MATCH (n) DELETE n"
        self.graph_store.conn.run(gql)

    def check_label(self, graph_elem_type: GraphElemType) -> bool:
        """Check if the label exists in the graph.

        Args:
            graph_elem_type (GraphElemType): The type of the graph element.

        Returns:
            True if the label exists in the specified graph element type, otherwise
            False.
        """
        tables = self.graph_store.conn.get_table_names()

        return graph_elem_type.value in tables

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
        search_scope: Optional[
            Literal["knowledge_graph", "document_graph"]
        ] = "knowledge_graph",
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if not subs:
            return MemoryGraph()

        if depth <= 0:
            depth = 3
        depth_string = f"1..{depth}"

        if limit is None:
            limit_string = ""
        else:
            limit_string = f"LIMIT {limit}"

        if search_scope == "knowledge_graph":
            if direct.name == "OUT":
                rel = f"-[r:{GraphElemType.RELATION.value}*{depth_string}]->"
            elif direct.name == "IN":
                rel = f"<-[r:{GraphElemType.RELATION.value}*{depth_string}]-"
            else:
                rel = f"-[r:{GraphElemType.RELATION.value}*{depth_string}]-"
            query = (
                f"MATCH p=(n:{GraphElemType.ENTITY.value})"
                f"{rel}(m:{GraphElemType.ENTITY.value}) "
                f"WHERE n.id IN {[self._escape_quotes(sub) for sub in subs]} "
                f"RETURN p {limit_string}"
            )
            return self.query(query=query, white_list=["description"])
        else:
            # If there exists the entities in the graph, return the graph that
            # includes the leaf chunks that connect to the entities, the chains from
            # documents to the leaf chunks, and the chain from documents to chunks;
            # document -> chunk -> chunk -> ... -> leaf chunk -> (entity)
            #
            # If not, return the graph that includes the chains from documents to chunks
            # that contain the subs (keywords).
            # document -> chunk -> chunk -> ... -> leaf chunk (that contains the subs)
            #
            # And only the leaf chunks contain the content, and the other chunks do not
            # contain any properties except the id, name.

            graph = MemoryGraph()

            # Check if the entities exist in the graph
            check_entity_query = (
                f"MATCH (n:{GraphElemType.ENTITY.value}) "
                f"WHERE n.id IN {[self._escape_quotes(sub) for sub in subs]} "
                "RETURN n"
            )
            if self.query(check_entity_query):
                # Query the leaf chunks in the chain from documents to chunks
                leaf_chunk_query = (
                    f"MATCH p=(n:{GraphElemType.CHUNK.value})-"
                    f"[r:{GraphElemType.INCLUDE.value}]->"
                    f"(m:{GraphElemType.ENTITY.value})"
                    f"WHERE m.name IN {[self._escape_quotes(sub) for sub in subs]} "
                    f"RETURN n"
                )
                graph_of_leaf_chunks = self.query(
                    query=leaf_chunk_query, white_list=["content"]
                )

                # Query the chain from documents to chunks,
                # document -> chunk -> ... ->  leaf_chunks
                chunk_names = [
                    self._escape_quotes(vertex.name)
                    for vertex in graph_of_leaf_chunks.vertices()
                ]
                chain_query = (
                    f"MATCH p=(n:{GraphElemType.DOCUMENT.value})-"
                    f"[:{GraphElemType.INCLUDE.value}*{depth_string}]->"
                    f"(m:{GraphElemType.CHUNK.value})"
                    f"WHERE m.name IN {chunk_names} "
                    "RETURN p"
                )
                # Filter all the properties by with_list
                graph.upsert_graph(self.query(query=chain_query, white_list=[""]))

                # The number of leaf chunks caompared to the `limit`
                if not limit or len(chunk_names) <= limit:
                    graph.upsert_graph(graph_of_leaf_chunks)
                else:
                    limited_leaf_chunk_query = leaf_chunk_query + f" {limit_string}"
                    graph.upsert_graph(
                        self.query(
                            query=limited_leaf_chunk_query, white_list=["content"]
                        )
                    )
            else:
                _subs_condition = " OR ".join(
                    [f"m.content CONTAINS '{self._escape_quotes(sub)}'" for sub in subs]
                )

                # Query the chain from documents to chunks,
                # document -> chunk -> chunk -> chunk -> ... -> chunk
                chain_query = (
                    f"MATCH p=(n:{GraphElemType.DOCUMENT.value})-"
                    f"[r:{GraphElemType.INCLUDE.value}*{depth_string}]->"
                    f"(m:{GraphElemType.CHUNK.value})"
                    f"WHERE {_subs_condition}"
                    "RETURN p"
                )
                # Filter all the properties by with_list
                graph.upsert_graph(self.query(query=chain_query, white_list=[""]))

                # Query the leaf chunks in the chain from documents to chunks
                leaf_chunk_query = (
                    f"MATCH p=(n:{GraphElemType.DOCUMENT.value})-"
                    f"[r:{GraphElemType.INCLUDE.value}*{depth_string}]->"
                    f"(m:{GraphElemType.CHUNK.value})"
                    f"WHERE {_subs_condition}"
                    f"RETURN m {limit_string}"
                )
                graph.upsert_graph(
                    self.query(query=leaf_chunk_query, white_list=["content"])
                )

            return graph

    def query(self, query: str, **kwargs) -> MemoryGraph:
        """Execute a query on graph.

        white_list: List[str] = kwargs.get("white_list", []), which contains the white
        list of properties and filters the properties that are not in the white list.
        """
        query_result = self.graph_store.conn.run(query=query)
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
        vertices, edges = self._get_nodes_edges_from_queried_data(
            query_result, white_list
        )

        mg = MemoryGraph()
        for vertex in vertices:
            mg.upsert_vertex(vertex)
        for edge in edges:
            mg.append_edge(edge)
        return mg

    # type: ignore[override]
    # mypy: ignore-errors
    async def stream_query(  # type: ignore[override]
        self,
        query: str,
        **kwargs,
    ) -> AsyncGenerator[Graph, None]:
        """Execute a stream query."""
        from neo4j import graph

        async for record in self.graph_store.conn.run_stream(query):  # type: ignore
            mg = MemoryGraph()
            for key in record.keys():
                value = record[key]
                if isinstance(value, graph.Node):
                    node_id = value._properties["id"]
                    description = value._properties["description"]
                    vertex = Vertex(vid=node_id, name=node_id, description=description)
                    mg.upsert_vertex(vertex)
                elif isinstance(value, graph.Relationship):
                    edge_nodes = value.nodes
                    prop_id = value._properties["id"]
                    assert edge_nodes and edge_nodes[0] and edge_nodes[1]
                    src_id = edge_nodes[0]._properties["id"]
                    dst_id = edge_nodes[1]._properties["id"]
                    description = value._properties["description"]
                    edge = Edge(
                        sid=src_id, tid=dst_id, name=prop_id, description=description
                    )
                    mg.append_edge(edge)
                elif isinstance(value, graph.Path):
                    nodes = list(record["p"].nodes)
                    rels = list(record["p"].relationships)
                    formatted_path = []
                    for i in range(len(nodes)):
                        formatted_path.append(
                            {
                                "id": nodes[i]._properties["id"],
                                "description": nodes[i]._properties["description"],
                            }
                        )
                        if i < len(rels):
                            formatted_path.append(
                                {
                                    "id": rels[i]._properties["id"],
                                    "description": rels[i]._properties["description"],
                                }
                            )
                    for i in range(0, len(formatted_path), 2):
                        mg.upsert_vertex(
                            Vertex(
                                vid=formatted_path[i]["id"],
                                name=formatted_path[i]["id"],
                                description=formatted_path[i]["description"],
                            )
                        )
                        if i + 2 < len(formatted_path):
                            mg.append_edge(
                                Edge(
                                    sid=formatted_path[i]["id"],
                                    tid=formatted_path[i + 2]["id"],
                                    name=formatted_path[i + 1]["id"],
                                    description=formatted_path[i + 1]["description"],
                                )
                            )
                else:
                    vertex = Vertex(
                        vid="json_node", name="json_node", description=value
                    )
                    mg.upsert_vertex(vertex)
            yield mg

    def _get_nodes_edges_from_queried_data(
        self,
        data: List[Dict[str, Any]],
        white_prop_list: List[str],
    ) -> Tuple[List[Vertex], List[Edge]]:
        """Format the query data.

        Args:
            data: The data to be formatted.
            white_prop_list: The white list of properties.

        Returns:
            Tuple[List[Vertex], List[Edge]]: The formatted vertices and edges.
        """
        vertex_list: List[Vertex] = []
        edge_list: List[Edge] = []

        # Remove id, src_id, dst_id and name from the white list
        # to avoid duplication in the initialisation of the vertex and edge
        _white_list = [
            prop
            for prop in white_prop_list
            if prop not in ["id", "src_id", "dst_id", "name"]
        ]

        from neo4j import graph

        def filter_properties(
            properties: dict[str, Any], white_list: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Filter the properties.

            It will remove the properties that are not in the white list.
            The expected propertities are:
                entity_properties = ["id", "name", "description", "_document_id",
                                        "_chunk_id", "_community_id"]
                edge_properties = ["id", "name", "description", "_chunk_id"]
            Args:
                properties: Dictionary of properties to filter
                white_list: List of properties to keep
                    - If None: Keep default properties (those not starting with '_'
                        and not in ['id', 'name'])
                    - If [""]: Remove all properties (return empty dict)
                    - If list of strings: Keep only properties in white_list
            """
            return (
                {}
                if white_list == [""]
                else {
                    key: value
                    for key, value in properties.items()
                    if (
                        (not key.startswith("_") and key not in ["id", "name"])
                        or (white_list is not None and key in white_list)
                    )
                }
            )

        # Parse the data to nodes and relationships
        for record in data:
            for value in record.values():
                if isinstance(value, graph.Node):
                    assert value._properties.get("id")
                    vertex = Vertex(
                        vid=value._properties.get("id", ""),
                        name=value._properties.get("name"),
                        **filter_properties(value._properties, _white_list),
                    )
                    if vertex not in vertex_list:
                        # TODO: Do we really need to check it every time?
                        vertex_list.append(vertex)
                elif isinstance(value, graph.Relationship):
                    for node in value.nodes:  # num of nodes is 2
                        assert node and node._properties
                        vertex = Vertex(
                            vid=node._properties.get("id", ""),
                            name=node._properties.get("name"),
                            **filter_properties(node._properties, _white_list),
                        )
                        if vertex not in vertex_list:
                            vertex_list.append(vertex)

                        assert value.nodes and value.nodes[0] and value.nodes[1]
                        edge = Edge(
                            sid=value.nodes[0]._properties.get("id", ""),
                            tid=value.nodes[1]._properties.get("id", ""),
                            name=value._properties.get("name", ""),
                            **filter_properties(value._properties, _white_list),
                        )
                        if edge not in edge_list:
                            edge_list.append(edge)
                elif isinstance(value, graph.Path):
                    for rel in value.relationships:
                        for node in rel.nodes:  # num of nodes is 2
                            assert node and node._properties
                            vertex = Vertex(
                                vid=node._properties.get("id", ""),
                                name=node._properties.get("name"),
                                **filter_properties(node._properties, _white_list),
                            )
                            if vertex not in vertex_list:
                                vertex_list.append(vertex)

                            assert rel.nodes and rel.nodes[0] and rel.nodes[1]
                            edge = Edge(
                                sid=rel.nodes[0]._properties.get("id", ""),
                                tid=rel.nodes[1]._properties.get("id", ""),
                                name=rel._properties.get("name", ""),
                                **filter_properties(rel._properties, _white_list),
                            )
                            if edge not in edge_list:
                                edge_list.append(edge)

                else:  # json_node
                    vertex = Vertex(
                        vid="json_node",
                        name="json_node",
                        **filter_properties({"description": value}, _white_list),
                    )
                    if vertex not in vertex_list:
                        vertex_list.append(vertex)
        return vertex_list, edge_list

    def _convert_dict_to_str(self, entity_list: List[Dict[str, Any]]) -> str:
        """Convert a list of entities to a formatted string representation."""
        formatted_nodes = [
            "{"
            + ", ".join(
                f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}"
                for k, v in node.items()
            )
            + "}"
            for node in entity_list
        ]
        return f"""{", ".join(formatted_nodes)}"""

    def _escape_quotes(self, value: str) -> str:
        """Escape single and double quotes in a string for queries."""
        if value is not None:
            return value.replace("'", "").replace('"', "")

    def upsert_doc_include_chunk(
        self,
        chunk: ParagraphChunk,
    ) -> None:
        """Convert chunk to document include chunk."""
        assert (
            chunk.chunk_parent_id and chunk.chunk_parent_name
        ), "Chunk parent ID and name are required (document_include_chunk)"

        edge = Edge(
            sid=chunk.chunk_parent_id,
            tid=chunk.chunk_id,
            name=GraphElemType.INCLUDE.value,
            edge_type=GraphElemType.DOCUMENT_INCLUDE_CHUNK.value,
        )

        self.upsert_edge(
            edges=iter([edge]),
            edge_type=GraphElemType.INCLUDE.value,
            src_type=GraphElemType.DOCUMENT.value,
            dst_type=GraphElemType.CHUNK.value,
        )

    def upsert_chunk_include_chunk(
        self,
        chunk: ParagraphChunk,
    ) -> None:
        """Convert chunk to chunk include chunk."""
        assert (
            chunk.chunk_parent_id and chunk.chunk_parent_name
        ), "Chunk parent ID and name are required (chunk_include_chunk)"

        edge = Edge(
            sid=chunk.chunk_parent_id,
            tid=chunk.chunk_id,
            name=GraphElemType.INCLUDE.value,
            edge_type=GraphElemType.CHUNK_INCLUDE_CHUNK.value,
        )

        self.upsert_edge(
            edges=iter([edge]),
            edge_type=GraphElemType.INCLUDE.value,
            src_type=GraphElemType.CHUNK.value,
            dst_type=GraphElemType.CHUNK.value,
        )

    def upsert_chunk_next_chunk(
        self, chunk: ParagraphChunk, next_chunk: ParagraphChunk
    ):
        """Uperst the vertices and the edge in chunk_next_chunk."""
        edge = Edge(
            sid=chunk.chunk_id,
            tid=next_chunk.chunk_id,
            name=GraphElemType.NEXT.value,
            edge_type=GraphElemType.CHUNK_NEXT_CHUNK.value,
        )

        self.upsert_edge(
            edges=iter([edge]),
            edge_type=GraphElemType.NEXT.value,
            src_type=GraphElemType.CHUNK.value,
            dst_type=GraphElemType.CHUNK.value,
        )

    def upsert_chunk_include_entity(
        self, chunk: ParagraphChunk, entity: Vertex
    ) -> None:
        """Convert chunk to chunk include entity."""
        edge = Edge(
            sid=chunk.chunk_id,
            tid=entity.vid,
            name=GraphElemType.INCLUDE.value,
            edge_type=GraphElemType.CHUNK_INCLUDE_ENTITY.value,
        )

        self.upsert_edge(
            edges=iter([edge]),
            edge_type=GraphElemType.INCLUDE.value,
            src_type=GraphElemType.CHUNK.value,
            dst_type=GraphElemType.ENTITY.value,
        )
