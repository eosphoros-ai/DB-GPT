"""Neo4j Community Store Adapter."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, Iterator, List, Optional, Tuple, Union

from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)
from dbgpt.storage.knowledge_graph.base import ParagraphChunk
from dbgpt_ext.storage.graph_store.neo4j_store import Neo4jStore
from dbgpt_ext.storage.knowledge_graph.community.base import (
    Community,
    GraphStoreAdapter,
)

logger = logging.getLogger(__name__)


class Neo4jStoreAdapter(GraphStoreAdapter):
    """Neo4j Community Store Adapter."""

    MAX_QUERY_LIMIT = 1000
    MAX_HIERARCHY_LEVEL = 3

    def __init__(self, graph_store: Neo4jStore):
        """Initialize Neo4j Community Store Adapter."""
        super().__init__(graph_store)

        # Create indexes for better performance
        self.create_graph(self.graph_store.get_config().name)

    async def discover_communities(self, **kwargs) -> List[str]:
        """Run community discovery.

        Note: Neo4j Graph Data Science library would be optimal for this.
        For now, we return communities based on existing _community_id values.
        """
        query = f"""
        MATCH (n:{self.get_vertex_type()})
        WHERE n._community_id IS NOT NULL
        RETURN DISTINCT n._community_id as community_id
        """
        result = self.graph_store.conn.run(query)
        community_ids = [
            record["community_id"] for record in result if record.get("community_id")
        ]
        logger.info(f"Discovered {len(community_ids)} communities.")
        return community_ids

    async def get_community(self, community_id: str) -> Community:
        """Get community."""
        query = (
            f"MATCH (n:{self.get_vertex_type()}) "
            f"WHERE n._community_id = $community_id "
            f"RETURN n"
        )
        edge_query = (
            f"MATCH (n:{self.get_vertex_type()})-"
            f"[r:{self.get_edge_type()}]-"
            f"(m:{self.get_vertex_type()}) "
            f"WHERE n._community_id = $community_id "
            f"RETURN n, r, m"
        )

        all_vertex_graph = self.query(query, community_id=community_id)
        all_edge_graph = self.query(edge_query, community_id=community_id)
        all_graph = MemoryGraph()
        for vertex in all_vertex_graph.vertices():
            all_graph.upsert_vertex(vertex)
        for edge in all_edge_graph.edges():
            all_graph.append_edge(edge)

        return Community(id=community_id, data=all_graph)

    @property
    def graph_store(self) -> Neo4jStore:
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
            f"WHERE n1.id = $subj "
            f"RETURN type(r) as rel, n2.id as obj"
        )
        data = self.graph_store.conn.run(triplet_query, subj=subj)
        return [(record["rel"], record["obj"]) for record in data]

    def get_document_vertex(self, doc_name: str) -> Vertex:
        """Get the document vertex in the graph."""
        query = f"""MATCH (n:{GraphElemType.DOCUMENT.value}) 
        WHERE n.name = $doc_name RETURN n LIMIT 1"""
        graph = self.query(query, doc_name=doc_name)
        if graph.vertex_count > 0:
            return list(graph.vertices())[0]
        return None

    async def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        try:
            # Get node labels
            node_query = "CALL db.labels()"
            labels = [
                record["label"] for record in self.graph_store.conn.run(node_query)
            ]

            # Get relationship types
            rel_query = "CALL db.relationshipTypes()"
            rel_types = [
                record["relationshipType"]
                for record in self.graph_store.conn.run(rel_query)
            ]

            schema = {
                "node_labels": labels,
                "relationship_types": rel_types,
            }

            return json.dumps(schema, indent=2)
        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            return "{}"

    def get_full_graph(self, limit: Optional[int] = None) -> Graph:
        """Get full graph."""
        if not limit:
            limit = self.MAX_QUERY_LIMIT
        if limit <= 0:
            raise ValueError("Limit must be greater than 0.")

        graph_result = self.query(f"MATCH (n)-[r]-(m) RETURN n, r, m LIMIT {limit}")
        full_graph = MemoryGraph()
        for vertex in graph_result.vertices():
            full_graph.upsert_vertex(vertex)
        for edge in graph_result.edges():
            full_graph.append_edge(edge)
        return full_graph

    def _escape_quotes(self, value: Any) -> str:
        """Escape quotes in string values."""
        if value is None:
            return ""
        return str(value).replace("'", "\\'").replace('"', '\\"')

    def upsert_entities(self, entities: Iterator[Vertex]) -> None:
        """Upsert entities."""
        for entity in entities:
            props = {
                "id": entity.vid,
                "name": entity.name or entity.vid,
                "description": entity.get_prop("description") or "",
                "_document_id": entity.get_prop("_document_id") or "0",
                "_chunk_id": entity.get_prop("_chunk_id") or "0",
                "_community_id": entity.get_prop("_community_id") or "0",
            }

            query = f"""
            MERGE (n:{GraphElemType.ENTITY.value} {{id: $id}})
            SET n += $props
            """
            self.graph_store.conn.run(query, id=entity.vid, props=props)

    def upsert_edge(
        self, edges: Iterator[Edge], edge_type: str, src_type: str, dst_type: str
    ) -> None:
        """Upsert edges."""
        for edge in edges:
            props = {
                "id": edge.name or f"{edge.sid}_{edge.tid}",
                "name": edge.name or edge_type,
                "description": edge.get_prop("description") or "",
                "_chunk_id": edge.get_prop("_chunk_id") or "",
            }

            query = f"""
            MATCH (src:{src_type} {{id: $sid}})
            MATCH (dst:{dst_type} {{id: $tid}})
            MERGE (src)-[r:{edge_type}]->(dst)
            SET r += $props
            """
            self.graph_store.conn.run(query, sid=edge.sid, tid=edge.tid, props=props)

    def upsert_chunks(self, chunks: Iterator[Union[Vertex, ParagraphChunk]]) -> None:
        """Upsert chunks."""
        for chunk in chunks:
            if isinstance(chunk, ParagraphChunk):
                props = {
                    "id": chunk.chunk_id,
                    "name": chunk.chunk_name or chunk.chunk_id,
                    "content": chunk.content or "",
                }
            else:
                props = {
                    "id": chunk.vid,
                    "name": chunk.name or chunk.vid,
                    "content": chunk.get_prop("content") or "",
                }

            query = f"""
            MERGE (n:{GraphElemType.CHUNK.value} {{id: $id}})
            SET n += $props
            """
            self.graph_store.conn.run(query, id=props["id"], props=props)

    def upsert_documents(
        self, documents: Iterator[Union[Vertex, ParagraphChunk]]
    ) -> None:
        """Upsert documents."""
        for document in documents:
            if isinstance(document, ParagraphChunk):
                props = {
                    "id": document.chunk_id,
                    "name": document.chunk_name or document.chunk_id,
                    "content": "",
                }
            else:
                props = {
                    "id": document.vid,
                    "name": document.name or document.vid,
                    "content": "",
                }

            query = f"""
            MERGE (n:{GraphElemType.DOCUMENT.value} {{id: $id}})
            SET n += $props
            """
            self.graph_store.conn.run(query, id=props["id"], props=props)

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        # Create subject and object entities
        query = f"""
        MERGE (s:{GraphElemType.ENTITY.value} {{id: $subj}})
        SET s.name = $subj
        MERGE (o:{GraphElemType.ENTITY.value} {{id: $obj}})
        SET o.name = $obj
        """
        self.graph_store.conn.run(query, subj=subj, obj=obj)

        # Create relationship
        edge_query = f"""
        MATCH (s:{GraphElemType.ENTITY.value} {{id: $subj}})
        MATCH (o:{GraphElemType.ENTITY.value} {{id: $obj}})
        MERGE (s)-[r:{GraphElemType.RELATION.value}]->(o)
        SET r.id = $rel, r.name = $rel
        """
        self.graph_store.conn.run(edge_query, subj=subj, obj=obj, rel=rel)

    def upsert_graph(self, graph: Graph) -> None:
        """Add graph to the graph store."""
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

    def upsert_doc_include_chunk(self, chunk: ParagraphChunk) -> None:
        """Convert chunk to document include chunk."""
        # Create document vertex
        doc_id = (
            f"doc_{chunk.chunk_name}" if chunk.chunk_name else f"doc_{chunk.chunk_id}"
        )
        doc_query = f"""
        MERGE (d:{GraphElemType.DOCUMENT.value} {{id: $doc_id}})
        SET d.name = $doc_name
        """
        self.graph_store.conn.run(
            query=doc_query, doc_id=doc_id, doc_name=chunk.chunk_name or doc_id
        )

        # Create chunk vertex
        chunk_query = f"""
        MERGE (c:{GraphElemType.CHUNK.value} {{id: $chunk_id}})
        SET c.name = $chunk_name, c.content = $content
        """
        self.graph_store.conn.run(
            query=chunk_query,
            chunk_id=chunk.chunk_id,
            chunk_name=chunk.chunk_name or chunk.chunk_id,
            content=chunk.content or "",
        )

        # Create relationship
        rel_query = f"""
        MATCH (d:{GraphElemType.DOCUMENT.value} {{id: $doc_id}})
        MATCH (c:{GraphElemType.CHUNK.value} {{id: $chunk_id}})
        MERGE (d)-[r:{GraphElemType.INCLUDE.value}]->(c)
        SET r.id = $rel_id, r.name = 'include'
        """
        self.graph_store.conn.run(
            query=rel_query,
            doc_id=doc_id,
            chunk_id=chunk.chunk_id,
            rel_id=f"{doc_id}_{chunk.chunk_id}",
        )

    def upsert_chunk_include_chunk(self, chunk: ParagraphChunk) -> None:
        """Convert chunk to chunk include chunk."""
        # This is typically used for hierarchical chunks
        # For now, we just ensure the chunk exists
        chunk_query = f"""
        MERGE (c:{GraphElemType.CHUNK.value} {{id: $chunk_id}})
        SET c.name = $chunk_name, c.content = $content
        """
        self.graph_store.conn.run(
            query=chunk_query,
            chunk_id=chunk.chunk_id,
            chunk_name=chunk.chunk_name or chunk.chunk_id,
            content=chunk.content or "",
        )

    def upsert_chunk_next_chunk(
        self, chunk: ParagraphChunk, next_chunk: ParagraphChunk
    ):
        """Upsert the vertices and the edge in chunk_next_chunk."""
        # Create both chunks
        for c in [chunk, next_chunk]:
            chunk_query = f"""
            MERGE (c:{GraphElemType.CHUNK.value} {{id: $chunk_id}})
            SET c.name = $chunk_name, c.content = $content
            """
            self.graph_store.conn.run(
                query=chunk_query,
                chunk_id=c.chunk_id,
                chunk_name=c.chunk_name or c.chunk_id,
                content=c.content or "",
            )

        # Create NEXT relationship
        rel_query = f"""
        MATCH (c1:{GraphElemType.CHUNK.value} {{id: $chunk_id1}})
        MATCH (c2:{GraphElemType.CHUNK.value} {{id: $chunk_id2}})
        MERGE (c1)-[r:{GraphElemType.NEXT.value}]->(c2)
        SET r.id = $rel_id, r.name = 'next'
        """
        self.graph_store.conn.run(
            query=rel_query,
            chunk_id1=chunk.chunk_id,
            chunk_id2=next_chunk.chunk_id,
            rel_id=f"{chunk.chunk_id}_{next_chunk.chunk_id}",
        )

    def upsert_chunk_include_entity(
        self, chunk: ParagraphChunk, entity: Vertex
    ) -> None:
        """Convert chunk to chunk include entity."""
        # Create chunk
        chunk_query = f"""
        MERGE (c:{GraphElemType.CHUNK.value} {{id: $chunk_id}})
        SET c.name = $chunk_name, c.content = $content
        """
        self.graph_store.conn.run(
            query=chunk_query,
            chunk_id=chunk.chunk_id,
            chunk_name=chunk.chunk_name or chunk.chunk_id,
            content=chunk.content or "",
        )

        # Create entity
        entity_query = f"""
        MERGE (e:{GraphElemType.ENTITY.value} {{id: $entity_id}})
        SET e.name = $entity_name
        """
        self.graph_store.conn.run(
            query=entity_query,
            entity_id=entity.vid,
            entity_name=entity.name or entity.vid,
        )

        # Create relationship
        rel_query = f"""
        MATCH (c:{GraphElemType.CHUNK.value} {{id: $chunk_id}})
        MATCH (e:{GraphElemType.ENTITY.value} {{id: $entity_id}})
        MERGE (c)-[r:{GraphElemType.INCLUDE.value}]->(e)
        SET r.id = $rel_id, r.name = 'include'
        """
        self.graph_store.conn.run(
            query=rel_query,
            chunk_id=chunk.chunk_id,
            entity_id=entity.vid,
            rel_id=f"{chunk.chunk_id}_{entity.vid}",
        )

    def delete_document(self, chunk_id: str) -> None:
        """Delete document in the graph."""
        chunkids_list = [c.strip() for c in chunk_id.split(",")]

        # Delete chunks
        del_chunk_query = f"""
        MATCH (n:{GraphElemType.CHUNK.value})
        WHERE n.id IN $chunk_ids
        DETACH DELETE n
        """
        self.graph_store.conn.run(del_chunk_query, chunk_ids=chunkids_list)

        # Delete relations related to these chunks
        del_relation_query = f"""
        MATCH (m:{GraphElemType.ENTITY.value})-[r:{GraphElemType.RELATION.value}]
        -(n:{GraphElemType.ENTITY.value})
        WHERE r._chunk_id IN $chunk_ids
        DELETE r
        """
        self.graph_store.conn.run(del_relation_query, chunk_ids=chunkids_list)

        # Delete orphan nodes
        delete_orphan_query = """
        MATCH (n)
        WHERE NOT EXISTS((n)-[]-())
        DELETE n
        """
        self.graph_store.conn.run(delete_orphan_query)

    def delete_triplet(self, sub: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        del_query = f"""
        MATCH (n1:{GraphElemType.ENTITY.value} {{id: $sub}})
        -[r:{GraphElemType.RELATION.value} {{id: $rel}}]->
        (n2:{GraphElemType.ENTITY.value} {{id: $obj}})
        DELETE r
        """
        self.graph_store.conn.run(query=del_query, sub=sub, rel=rel, obj=obj)

    def drop(self):
        """Delete Graph."""
        self.truncate()

    def create_graph(self, graph_name: str):
        """Create indexes for the graph.

        Note: In Neo4j, we don't create separate graphs like in TuGraph.
        All data is stored in the configured database, and we use labels
        to organize different knowledge spaces.
        """
        logger.info(f"Setting up Neo4j for knowledge space: {graph_name}")

        # Create indexes for common properties
        # Note: These run on the database specified in the connection config
        indexes = [
            f"CREATE INDEX IF NOT EXISTS FOR (n:{GraphElemType.ENTITY.value}) ON"
            f" (n.id)",
            f"CREATE INDEX IF NOT EXISTS FOR (n:{GraphElemType.ENTITY.value}) ON"
            f" (n._community_id)",
            f"CREATE INDEX IF NOT EXISTS FOR (n:{GraphElemType.CHUNK.value}) ON (n.id)",
            f"CREATE INDEX IF NOT EXISTS FOR (n:{GraphElemType.CHUNK.value}) ON"
            f" (n.content)",
            f"CREATE INDEX IF NOT EXISTS FOR (n:{GraphElemType.DOCUMENT.value}) ON"
            f" (n.id)",
            f"CREATE INDEX IF NOT EXISTS FOR (n:{GraphElemType.DOCUMENT.value}) ON"
            f" (n.name)",
        ]

        for index_query in indexes:
            try:
                self.graph_store.conn.run(index_query)
                logger.info("Successfully created/verified index")
            except Exception as e:
                # Log as info instead of warning - indexes might already exist
                logger.info(f"Index creation note: {str(e)[:200]}")
                # Continue even if index creation fails - it might already exist

    def create_graph_label(
        self,
        graph_elem_type: GraphElemType,
        graph_properties: List[Dict[str, Union[str, bool]]],
    ) -> None:
        """Create a graph label.

        Neo4j creates labels dynamically, so we just log this for compatibility.
        """
        logger.info(f"Neo4j: Label {graph_elem_type.value} will be created dynamically")

    def truncate(self):
        """Truncate Graph."""
        logger.warning("Truncating all data from Neo4j database")

        # Delete all relationships first
        self.graph_store.conn.run("MATCH ()-[r]->() DELETE r")

        # Then delete all nodes
        self.graph_store.conn.run("MATCH (n) DELETE n")

    def check_label(self, graph_elem_type: GraphElemType) -> bool:
        """Check if the label exists in the graph."""
        try:
            query = "CALL db.labels()"
            labels = [record[0] for record in self.graph_store.conn.run(query)]
            return graph_elem_type.value in labels
        except Exception as e:
            logger.warning(f"Failed to check label: {e}")
            return False

    def explore_trigraph(
        self,
        subs: Union[List[str], List[List[float]]],
        topk: Optional[int] = None,
        score_threshold: Optional[float] = None,
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if not subs:
            return MemoryGraph()

        if depth <= 0:
            depth = 3

        if limit is None:
            limit = self.MAX_QUERY_LIMIT

        # Convert direction
        if direct == Direction.OUT:
            direction_str = ">"
        elif direct == Direction.IN:
            direction_str = "<"
        else:
            direction_str = ""

        # Build query for each subject
        result_graph = MemoryGraph()

        for sub in subs:
            if isinstance(sub, list):
                # Embedding search not yet implemented for Neo4j
                continue

            query = f"""
            MATCH path = (start:{GraphElemType.ENTITY.value} {{id: $sub}})
            -[*1..{depth}]-{direction_str}(end)
            RETURN nodes(path) as nodes, relationships(path) as rels
            LIMIT {limit}
            """

            try:
                results = self.graph_store.conn.run(query, sub=sub)
                for record in results:
                    # Process nodes
                    for node in record.get("nodes", []):
                        vertex = self._neo4j_node_to_vertex(node)
                        result_graph.upsert_vertex(vertex)

                    # Process relationships
                    for rel in record.get("rels", []):
                        edge = self._neo4j_relationship_to_edge(rel)
                        result_graph.append_edge(edge)
            except Exception as e:
                logger.error(f"Failed to explore trigraph: {e}")

        return result_graph

    def explore_docgraph_with_entities(
        self,
        subs: List[str],
        topk: Optional[int] = None,
        score_threshold: Optional[float] = None,
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if not subs:
            return MemoryGraph()

        if limit is None:
            limit = self.MAX_QUERY_LIMIT

        result_graph = MemoryGraph()

        for sub in subs:
            # Find chunks connected to this entity
            query = f"""
            MATCH (e:{GraphElemType.ENTITY.value} {{id: $sub}})
            <-[:{GraphElemType.INCLUDE.value}]-
            (c:{GraphElemType.CHUNK.value})
            <-[:{GraphElemType.INCLUDE.value}]-
            (d:{GraphElemType.DOCUMENT.value})
            RETURN e, c, d
            LIMIT {limit}
            """

            try:
                results = self.graph_store.conn.run(query, sub=sub)
                for record in results:
                    for key in ["e", "c", "d"]:
                        if key in record and record[key]:
                            vertex = self._neo4j_node_to_vertex(record[key])
                            result_graph.upsert_vertex(vertex)
            except Exception as e:
                logger.error(f"Failed to explore docgraph: {e}")

        return result_graph

    def explore_docgraph_without_entities(
        self,
        subs: Union[List[str], List[List[float]]],
        topk: Optional[int] = None,
        score_threshold: Optional[float] = None,
        direct: Direction = Direction.BOTH,
        depth: int = 3,
        fan: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> MemoryGraph:
        """Explore the graph from given subjects up to a depth."""
        if not subs:
            return MemoryGraph()

        if limit is None:
            limit = self.MAX_QUERY_LIMIT

        result_graph = MemoryGraph()

        for sub in subs:
            if isinstance(sub, list):
                # Embedding search not yet implemented
                continue

            # Find chunks containing the keyword
            query = f"""
            MATCH (c:{GraphElemType.CHUNK.value})
            WHERE c.content CONTAINS $keyword
            MATCH (d:{GraphElemType.DOCUMENT.value})
            -[:{GraphElemType.INCLUDE.value}]->(c)
            RETURN c, d
            LIMIT {limit}
            """

            try:
                results = self.graph_store.conn.run(query, keyword=sub)
                for record in results:
                    for key in ["c", "d"]:
                        if key in record and record[key]:
                            vertex = self._neo4j_node_to_vertex(record[key])
                            result_graph.upsert_vertex(vertex)
            except Exception as e:
                logger.error(f"Failed to explore docgraph: {e}")

        return result_graph

    def query(self, query: str, **kwargs) -> MemoryGraph:
        """Execute a Cypher query and return results as a MemoryGraph."""
        graph = MemoryGraph()

        try:
            results = self.graph_store.conn.run(query, **kwargs)

            for record in results:
                # Process each value in the record
                for key, value in record.items():
                    if value is None:
                        continue
                    if hasattr(value, "labels"):  # It's a node
                        vertex = self._neo4j_node_to_vertex(value)
                        graph.upsert_vertex(vertex)
                    elif hasattr(value, "type"):  # It's a relationship
                        edge = self._neo4j_relationship_to_edge(value)
                        graph.append_edge(edge)

        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")

        return graph

    async def stream_query(self, query: str, **kwargs) -> AsyncGenerator[Graph, None]:
        """Execute a stream query."""
        # For now, return the full result as a single graph
        result = self.query(query, **kwargs)
        yield result

    def _neo4j_node_to_vertex(self, node) -> Vertex:
        """Convert a Neo4j node to a Vertex."""
        props = dict(node.items())
        vertex_id = props.get("id", str(node.id))
        labels = list(node.labels)

        if labels:
            props["vertex_type"] = labels[0]

        return Vertex(vid=vertex_id, props=props)

    def _neo4j_relationship_to_edge(self, rel) -> Edge:
        """Convert a Neo4j relationship to an Edge."""
        props = dict(rel.items())
        props["edge_type"] = rel.type

        # Get source and target node custom IDs (not internal Neo4j IDs)
        # Nodes are stored with custom 'id' property, must use that for consistency
        start_node = rel.start_node if hasattr(rel, "start_node") else rel.nodes[0]
        end_node = rel.end_node if hasattr(rel, "end_node") else rel.nodes[1]

        # Extract custom 'id' property from nodes, fallback to internal id if missing
        sid = str(dict(start_node.items()).get("id", start_node.id))
        tid = str(dict(end_node.items()).get("id", end_node.id))

        # Edge requires name as a positional parameter
        # Remove 'name' from props to avoid passing it twice
        edge_name = props.pop("name", rel.type)
        return Edge(sid, tid, edge_name, **props)
