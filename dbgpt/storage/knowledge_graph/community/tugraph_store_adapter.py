"""TuGraph Community Store Adapter."""

import json
import logging
from typing import Dict, Iterator, List, Optional, Tuple

from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)
from dbgpt.storage.graph_store.tugraph_store import TuGraphStore, TuGraphStoreConfig
from dbgpt.storage.knowledge_graph.community.base import Community, GraphStoreAdapter

logger = logging.getLogger(__name__)


class TuGraphStoreAdapter(GraphStoreAdapter):
    """TuGraph Community Store Adapter."""

    MAX_HIERARCHY_LEVEL = 3

    def __init__(self, summary_enabled: bool = False):
        """Initialize TuGraph Community Store Adapter."""
        self._graph_store = TuGraphStore(TuGraphStoreConfig())
        self._summary_enabled = summary_enabled

        super().__init__(self._graph_store)

        # Create the graph
        self.create_graph(self._graph_store.get_config().name)

    ####################
    #
    #
    # TuGraph Community Store
    #
    #
    ####################
    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery with leiden."""
        mg = self._graph_store.query(
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

        all_vertex_graph = self._graph_store.query(query)
        all_edge_graph = self._graph_store.query(edge_query)
        all_graph = MemoryGraph()
        for vertex in all_vertex_graph.vertices():
            all_graph.upsert_vertex(vertex)
        for edge in all_edge_graph.edges():
            all_graph.append_edge(edge)

        return Community(id=community_id, data=all_graph)

    ####################
    #
    #
    # TuGraph Store
    #
    #
    ####################
    def get_graph_config(self):
        """Get the graph store config."""
        return self._graph_store.get_config()

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
        data = self._graph_store.conn.run(triplet_query)
        return [(record["rel"], record["obj"]) for record in data]

    def get_document_vertex(self, doc_name: str) -> Vertex:
        """Get the document vertex in the graph."""
        gql = f"""MATCH (n) WHERE n.id = {doc_name} RETURN n"""
        graph = self._graph_store.query(gql)
        vertex = graph.get_vertex(doc_name)
        return vertex

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        query = "CALL dbms.graph.getGraphSchema()"
        data = self._graph_store.conn.run(query=query)
        schema = data[0]["schema"]
        return schema

    def get_full_graph(self, limit: int) -> Graph:
        """Get full graph."""
        if limit <= 0:
            raise ValueError("Limit must be greater than 0.")
        graph_result = self._graph_store.query(
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
                "id": self._graph_store._escape_quotes(entity.vid),
                "name": self._graph_store._escape_quotes(entity.name),
                "description": self._graph_store._escape_quotes(
                    entity.get_prop("description")
                )
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
            f"[{self._graph_store._parser(entity_list)}])"
        )
        self._graph_store.conn.run(query=entity_query)

    def upsert_edge(
        self, edges: Iterator[Edge], edge_type: str, src_type: str, dst_type: str
    ) -> None:
        """Upsert edges."""
        edge_list = [
            {
                "sid": self._graph_store._escape_quotes(edge.sid),
                "tid": self._graph_store._escape_quotes(edge.tid),
                "id": self._graph_store._escape_quotes(edge.name),
                "name": self._graph_store._escape_quotes(edge.name),
                "description": self._graph_store._escape_quotes(
                    edge.get_prop("description")
                )
                or "",
                "_chunk_id": self._graph_store._escape_quotes(
                    edge.get_prop("_chunk_id")
                )
                or "",
            }
            for edge in edges
        ]
        relation_query = f"""CALL db.upsertEdge("{edge_type}",
            {{type:"{src_type}", key:"sid"}},
            {{type:"{dst_type}", key:"tid"}},
            [{self._graph_store._parser(edge_list)}])"""
        self._graph_store.conn.run(query=relation_query)

    def upsert_chunks(self, chunks: Iterator[Vertex]) -> None:
        """Upsert chunks."""
        chunk_list = [
            {
                "id": self._graph_store._escape_quotes(chunk.vid),
                "name": self._graph_store._escape_quotes(chunk.name),
                "content": self._graph_store._escape_quotes(chunk.get_prop("content")),
            }
            for chunk in chunks
        ]
        chunk_query = (
            f"CALL db.upsertVertex("
            f'"{GraphElemType.CHUNK.value}", '
            f"[{self._graph_store._parser(chunk_list)}])"
        )
        self._graph_store.conn.run(query=chunk_query)

    def upsert_documents(self, documents: Iterator[Vertex]) -> None:
        """Upsert documents."""
        document_list = [
            {
                "id": self._graph_store._escape_quotes(document.vid),
                "name": self._graph_store._escape_quotes(document.name),
                "content": self._graph_store._escape_quotes(
                    document.get_prop("content")
                )
                or "",
            }
            for document in documents
        ]
        document_query = (
            f"CALL db.upsertVertex("
            f'"{GraphElemType.DOCUMENT.value}", '
            f"[{self._graph_store._parser(document_list)}])"
        )
        self._graph_store.conn.run(query=document_query)

    def upsert_relations(self, relations: Iterator[Edge]) -> None:
        """Upsert relations."""
        pass

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

        self._graph_store.conn.run(query=vertex_query)
        self._graph_store.conn.run(query=edge_query)

    def insert_graph(self, graph: Graph) -> None:
        """Add graph to the graph store.

        Args:
            graph (Graph): The graph to be added.
        """
        # Get the iterators of all the vertices and the edges from the graph
        documents: Iterator[Vertex] = graph.vertices(
            filter_fn=lambda x: x.type == GraphElemType.DOCUMENT.value
        )
        doc_include_chunk: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.type == "doc_include_chunk"
        )
        chunks: Iterator[Vertex] = graph.vertices(
            filter_fn=lambda x: x.type == GraphElemType.CHUNK.value
        )
        chunk_include_chunk: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.type == "chunk_include_chunk"
        )
        chunk_next_chunk: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.type == "chunk_next_chunk"
        )
        entities: Iterator[Vertex] = graph.vertices(
            filter_fn=lambda x: x.type == GraphElemType.ENTITY.value
        )
        chunk_include_entity: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.type == "chunk_include_entity"
        )
        relation: Iterator[Edge] = graph.edges(
            filter_fn=lambda x: x.type == GraphElemType.RELATION.value
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
        self._graph_store.conn.run(del_chunk_gql)
        self._graph_store.conn.run(del_relation_gql)
        self._graph_store.conn.run(delete_only_vertex)

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        del_query = (
            f"MATCH (n1:{GraphElemType.ENTITY.value} {{id:'{sub}'}})"
            f"-[r:{GraphElemType.RELATION.value} {{id:'{rel}'}}]->"
            f"(n2:{GraphElemType.ENTITY.value} {{id:'{obj}'}}) DELETE n1,n2,r"
        )
        self._graph_store.conn.run(query=del_query)

    def drop(self):
        """Delete Graph."""
        self._graph_store.conn.delete_graph(self.get_graph_config().name)

    def create_graph(self, graph_name: str):
        """Create a graph."""
        self._graph_store.conn.create_graph(graph_name=graph_name)

        # Create the graph schema
        # TODO: Move the schema creation to the base class. (adapter)
        def _format_graph_propertity_schema(
            name: str,
            type: str = "STRING",
            optional: bool = False,
            index: bool = None,
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
        document_proerties = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_community_id", "STRING", True, True),
        ]
        self.create_graph_label(
            elem_type=GraphElemType.DOCUMENT, graph_properties=document_proerties
        )

        # Create the graph label for chunk vertex
        chunk_proerties = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_community_id", "STRING", True, True),
            _format_graph_propertity_schema("content", "STRING", True, True),
        ]
        self.create_graph_label(
            elem_type=GraphElemType.CHUNK, graph_properties=chunk_proerties
        )

        # Create the graph label for entity vertex
        vertex_proerties = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_community_id", "STRING", True, True),
            _format_graph_propertity_schema("description", "STRING", True, True),
        ]
        self.create_graph_label(
            elem_type=GraphElemType.ENTITY, graph_properties=vertex_proerties
        )

        # Create the graph label for relation edge
        edge_proerties = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("_chunk_id", "STRING", True, True),
            _format_graph_propertity_schema("description", "STRING", True, True),
        ]
        self.create_graph_label(
            elem_type=GraphElemType.RELATION, graph_properties=edge_proerties
        )

        # Create the graph label for include edge
        include_proerties = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("description", "STRING", True),
        ]
        self.create_graph_label(
            elem_type=GraphElemType.INCLUDE, graph_properties=include_proerties
        )

        # Create the graph label for next edge
        next_proerties = [
            _format_graph_propertity_schema("id", "STRING", False),
            _format_graph_propertity_schema("name", "STRING", False),
            _format_graph_propertity_schema("description", "STRING", True),
        ]
        self.create_graph_label(
            elem_type=GraphElemType.NEXT, graph_properties=next_proerties
        )

        if self._summary_enabled:
            self._graph_store._upload_plugin()

    def create_graph_label(
        self,
        graph_elem_type: GraphElemType,
        graph_properties: Dict[str, str | bool],
    ):
        """Create a graph label.

        The graph label is used to identify and distinguish different types of nodes
        (vertices) and edges in the graph.

        Args:
            graph_elem_type (GraphElemType): The type of the graph element.
            graph_properties (Dict[str, str|bool]): The properties of the graph element.
        """
        if not self._check_label(graph_elem_type):
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
                data = json.dumps(
                    {
                        "label": graph_elem_type.va2lue,
                        "type": "EDGE",
                        "constraints": [
                            [GraphElemType.ENTITY.value, GraphElemType.ENTITY.value]
                        ],
                        "properties": graph_properties,
                    }
                )
                gql = f"""CALL db.createEdgeLabelByJson('{data}')"""
            self._graph_store.conn.run(gql)

    def truncate(self):
        """Truncate Graph."""
        gql = "MATCH (n) DELETE n"
        self._graph_store.conn.run(gql)

    def check_label(self, graph_elem_type: GraphElemType) -> bool:
        """Check if the label exists in the graph.

        Args:
            graph_elem_type (GraphElemType): The type of the graph element.

        Returns:
            True if the label exists in the specified graph element type, otherwise
            False.
        """
        vertex_tables, edge_tables = self._graph_store.conn.get_table_names()

        if graph_elem_type.is_vertex():
            return graph_elem_type in vertex_tables
        else:
            return graph_elem_type in edge_tables

    def explore(
        self,
        subs: List[str],
        direct: Direction = Direction.BOTH,
        depth: int | None = None,
        fan: int | None = None,
        limit: int | None = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if not subs:
            return MemoryGraph()

        if fan is not None:
            raise ValueError("Fan functionality is not supported at this time.")
        else:
            depth_string = f"1..{depth}"
            if depth is None:
                depth_string = ".."

            limit_string = f"LIMIT {limit}"
            if limit is None:
                limit_string = ""
            if direct.name == "OUT":
                rel = f"-[r:{GraphElemType.RELATION.value}*{depth_string}]->"
            elif direct.name == "IN":
                rel = f"<-[r:{GraphElemType.RELATION.value}*{depth_string}]-"
            else:
                rel = f"-[r:{GraphElemType.RELATION.value}*{depth_string}]-"
            query = (
                f"MATCH p=(n:{GraphElemType.ENTITY.value})"
                f"{rel}(m:{GraphElemType.ENTITY.value}) "
                f"WHERE n.id IN {subs} RETURN p {limit_string}"
            )
            return self._graph_store.query(query)

    def explore_text_link(
        self,
        subs: List[str],
        depth: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Graph:
        """Explore the graph text link."""
        depth_string = f"1..{depth}" if depth is not None else ".."
        limit_string = f"LIMIT {limit}" if limit is not None else ""

        graph = MemoryGraph()

        for sub in subs:
            query = (
                f"MATCH p=(n:{GraphElemType.DOCUMENT.value})-"
                f"[r:{GraphElemType.INCLUDE.value}*{depth_string}]-"
                f"(m:{GraphElemType.CHUNK.value})WHERE m.content CONTAINS '{sub}' "
                f"RETURN p {limit_string}"
            )
            result = self._graph_store.query(query)
            for vertex in result.vertices():
                graph.upsert_vertex(vertex)
            for edge in result.edges():
                graph.append_edge(edge)

        return graph
