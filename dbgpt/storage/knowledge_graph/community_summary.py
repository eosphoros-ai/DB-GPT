"""Define the CommunitySummaryKnowledgeGraph."""

import logging
import os
import uuid
from typing import List, Optional, Tuple

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.rag.transformer.graph_extractor import GraphExtractor
from dbgpt.storage.knowledge_graph.base import ParagraphChunk
from dbgpt.storage.knowledge_graph.community.community_store import CommunityStore
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.factory import VectorStoreFactory
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class CommunitySummaryKnowledgeGraphConfig(BuiltinKnowledgeGraphConfig):
    """Community summary knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_store_type: str = Field(
        default="Chroma",
        description="The type of vector store.",
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description=(
            "The password of vector store, "
            "if not set, will use the default password."
        ),
    )
    extract_topk: int = Field(
        default=5,
        description="Topk of knowledge graph extract",
    )
    extract_score_threshold: float = Field(
        default=0.3,
        description="Recall score of knowledge graph extract",
    )
    community_topk: int = Field(
        default=50,
        description="Topk of community search in knowledge graph",
    )
    community_score_threshold: float = Field(
        default=0.0,
        description="Recall score of community search in knowledge graph",
    )
    triplet_graph_enabled: bool = Field(
        default=True,
        description="Enable the graph search for triplets",
    )
    document_graph_enabled: bool = Field(
        default=True,
        description="Enable the graph search for documents and chunks",
    )

    knowledge_graph_chunk_search_top_size: int = Field(
        default=5,
        description="Top size of knowledge graph chunk search",
    )
    knowledge_graph_extraction_batch_size: int = Field(
        default=20,
        description="Batch size of triplets extraction from the text",
    )


class CommunitySummaryKnowledgeGraph(BuiltinKnowledgeGraph):
    """Community summary knowledge graph class."""

    def __init__(self, config: CommunitySummaryKnowledgeGraphConfig):
        """Initialize community summary knowledge graph class."""
        super().__init__(config)
        self._config = config

        self._vector_store_type = os.getenv(
            "VECTOR_STORE_TYPE", config.vector_store_type
        )
        self._extract_topk = int(
            os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE", config.extract_topk)
        )
        self._extract_score_threshold = float(
            os.getenv(
                "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE",
                config.extract_score_threshold,
            )
        )
        self._community_topk = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_TOP_SIZE", config.community_topk
            )
        )
        self._community_score_threshold = float(
            os.getenv(
                "KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_RECALL_SCORE",
                config.community_score_threshold,
            )
        )
        self._document_graph_enabled = (
            os.environ["DOCUMENT_GRAPH_ENABLED"].lower() == "true"
            if "DOCUMENT_GRAPH_ENABLED" in os.environ
            else config.document_graph_enabled
        )
        self._triplet_graph_enabled = (
            os.environ["TRIPLET_GRAPH_ENABLED"].lower() == "true"
            if "TRIPLET_GRAPH_ENABLED" in os.environ
            else config.triplet_graph_enabled
        )
        self._knowledge_graph_chunk_search_top_size = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_CHUNK_SEARCH_TOP_SIZE",
                config.knowledge_graph_chunk_search_top_size,
            )
        )
        self._triplet_extraction_batch_size = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_EXTRACTION_BATCH_SIZE",
                config.knowledge_graph_extraction_batch_size,
            )
        )

        def extractor_configure(name: str, cfg: VectorStoreConfig):
            cfg.name = name
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password
            cfg.topk = self._extract_topk
            cfg.score_threshold = self._extract_score_threshold

        self._graph_extractor = GraphExtractor(
            self._llm_client,
            self._model_name,
            VectorStoreFactory.create(
                self._vector_store_type,
                config.name + "_CHUNK_HISTORY",
                extractor_configure,
            ),
        )

        def community_store_configure(name: str, cfg: VectorStoreConfig):
            cfg.name = name
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password
            cfg.topk = self._community_topk
            cfg.score_threshold = self._community_score_threshold

        self._community_store = CommunityStore(
            self._graph_store_apdater,
            CommunitySummarizer(self._llm_client, self._model_name),
            VectorStoreFactory.create(
                self._vector_store_type,
                config.name + "_COMMUNITY_SUMMARY",
                community_store_configure,
            ),
        )

    def get_config(self) -> BuiltinKnowledgeGraphConfig:
        """Get the knowledge graph config."""
        return self._config

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist graph from the document file."""
        await self._aload_document_graph(chunks)
        await self._aload_triplet_graph(chunks)
        await self._community_store.build_communities()

        return [chunk.chunk_id for chunk in chunks]

    async def _aload_document_graph(self, chunks: List[Chunk]) -> None:
        """Load the knowledge graph from the chunks.

        The chunks include the doc structure.
        """
        if not self._document_graph_enabled:
            return

        _chunks: List[ParagraphChunk] = [
            ParagraphChunk.model_validate(chunk.model_dump()) for chunk in chunks
        ]
        documment_chunk, paragraph_chunks = self._load_chunks(_chunks)

        # upsert the document and chunks vertices
        self._graph_store_apdater.upsert_documents(iter([documment_chunk]))
        self._graph_store_apdater.upsert_chunks(iter(paragraph_chunks))

        # upsert the document structure
        for chunk_index, chunk in enumerate(paragraph_chunks):
            # document -> include -> chunk
            if chunk.parent_is_document:
                self._graph_store_apdater.upsert_doc_include_chunk(chunk=chunk)
            else:  # chunk -> include -> chunk
                self._graph_store_apdater.upsert_chunk_include_chunk(chunk=chunk)

            # chunk -> next -> chunk
            if chunk_index >= 1:
                self._graph_store_apdater.upsert_chunk_next_chunk(
                    chunk=paragraph_chunks[chunk_index - 1], next_chunk=chunk
                )

    async def _aload_triplet_graph(self, chunks: List[Chunk]) -> None:
        """Load the knowledge graph from the chunks.

        The chunks include the doc structure.
        """
        if not self._triplet_graph_enabled:
            return

        document_graph_enabled = self._document_graph_enabled

        # Extract the triplets from the chunks, and return the list of graphs
        # in the same order as the input texts
        graphs_list = await self._graph_extractor.batch_extract(
            [chunk.content for chunk in chunks],
            batch_size=self._triplet_extraction_batch_size,
        )

        # Upsert the graphs into the graph store
        for idx, graphs in enumerate(graphs_list):
            for graph in graphs:
                if document_graph_enabled:
                    # Append the chunk id to the edge
                    for edge in graph.edges():
                        edge.set_prop("_chunk_id", chunks[idx].chunk_id)
                        graph.append_edge(edge=edge)

                # Upsert the graph
                self._graph_store_apdater.upsert_graph(graph)

                # chunk -> include -> entity
                if document_graph_enabled:
                    for vertex in graph.vertices():
                        self._graph_store_apdater.upsert_chunk_include_entity(
                            chunk=chunks[idx], entity=vertex
                        )

    def _load_chunks(
        self, chunks: List[ParagraphChunk]
    ) -> Tuple[ParagraphChunk, List[ParagraphChunk]]:
        """Load the chunks, and add the parent-child relationship within chunks."""
        # init default document
        doc_id = str(uuid.uuid4())
        doc_name = os.path.basename(chunks[0].metadata["source"] or "Text_Node")
        doc_chunk = ParagraphChunk(
            chunk_id=doc_id,
            chunk_name=doc_name,
        )

        # chunk.metadata = {"Header0": "title", "Header1": "title", ..., "source": "source_path"}  # noqa: E501
        for chunk_index, chunk in enumerate(chunks):
            parent = None
            directory_keys = list(chunk.metadata.keys())[
                :-1
            ]  # ex: ['Header0', 'Header1', 'Header2', ...]
            parent_level = directory_keys[-2] if len(directory_keys) > 1 else None
            current_level = directory_keys[-1] if directory_keys else "Header0"

            chunk.chunk_name = chunk.metadata.get(current_level, "none_header_chunk")

            # Find the parent chunk for every chunk
            # parent chunk -> chunk
            if parent_level:
                for parent_direct in reversed(directory_keys[:-1]):
                    parent_titile = chunk.metadata.get(parent_direct, None)
                    for n in reversed(range(chunk_index)):
                        metadata = chunks[n].metadata
                        keys = list(metadata.keys())[:-1]
                        if (
                            metadata
                            and parent_direct == keys[-1]
                            and parent_titile == metadata.get(parent_direct)
                        ):
                            parent = chunks[n]
                            chunk.chunk_parent_id = parent.chunk_id
                            chunk.chunk_parent_name = parent_titile
                            chunk.parent_content = parent.content
                            break
                        if chunk_index - n > len(directory_keys):
                            break
                    if chunk.chunk_parent_id:
                        break

            if not chunk.chunk_parent_id:
                chunk.chunk_parent_id = doc_id
                chunk.chunk_parent_name = doc_name
                chunk.parent_content = ""
                chunk.parent_is_document = True

        return doc_chunk, chunks

    async def asimilar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve relevant community summaries."""
        # Global search: retrieve relevant community summaries
        communities = await self._community_store.search_communities(text)
        summaries = [
            f"Section {i + 1}:\n{community.summary}"
            for i, community in enumerate(communities)
        ]
        context = "\n".join(summaries) if summaries else ""

        keywords: List[str] = await self._keyword_extractor.extract(text)
        subgraph = None
        subgraph_for_doc = None

        # Local search: extract keywords and explore subgraph
        triplet_graph_enabled = self._triplet_graph_enabled
        document_graph_enabled = self._document_graph_enabled

        if triplet_graph_enabled:
            subgraph = self._graph_store_apdater.explore(
                subs=keywords, limit=topk, search_scope="knowledge_graph"
            )

            if document_graph_enabled:
                keywords_for_document_graph = keywords
                for vertex in subgraph.vertices():
                    keywords_for_document_graph.append(vertex.name)

                subgraph_for_doc = self._graph_store_apdater.explore(
                    subs=keywords_for_document_graph,
                    limit=self._knowledge_graph_chunk_search_top_size,
                    search_scope="document_graph",
                )
        else:
            if document_graph_enabled:
                subgraph_for_doc = self._graph_store_apdater.explore(
                    subs=keywords,
                    limit=self._knowledge_graph_chunk_search_top_size,
                    search_scope="document_graph",
                )
        knowledge_graph_str = subgraph.format() if subgraph else ""
        knowledge_graph_for_doc_str = (
            subgraph_for_doc.format() if subgraph_for_doc else ""
        )

        logger.info(f"Search subgraph from the following keywords:\n{len(keywords)}")

        if not (summaries or knowledge_graph_str or knowledge_graph_for_doc_str):
            return []

        # merge search results into context
        content = HYBRID_SEARCH_PT.format(
            context=context,
            knowledge_graph=knowledge_graph_str,
            knowledge_graph_for_doc=knowledge_graph_for_doc_str,
        )
        logger.info(f"Final GraphRAG queried prompt:\n{content}")
        return [Chunk(content=content)]

    def truncate(self) -> List[str]:
        """Truncate knowledge graph."""
        logger.info("Truncate community store")
        self._community_store.truncate()
        logger.info("Truncate keyword extractor")
        self._keyword_extractor.truncate()
        logger.info("Truncate triplet extractor")
        self._graph_extractor.truncate()
        return [self._config.name]

    def delete_vector_name(self, index_name: str):
        """Delete knowledge graph."""
        logger.info("Drop community store")
        self._community_store.drop()

        logger.info("Drop keyword extractor")
        self._keyword_extractor.drop()

        logger.info("Drop triplet extractor")
        self._graph_extractor.drop()


HYBRID_SEARCH_PT = """
=====
The following information from [Context], [Knowledge Graph], and [Original Text From RAG] can help you answer user questions better.

[Context]:
{context}

[Knowledge Graph]:
{knowledge_graph}

[Original Text From RAG]
{knowledge_graph_for_doc}
=====

You are very good at combining the [Context] information provided by the prompt word template with the [Knowledge Graph] information,
answering the user's questions accurately and appropriately, and ensuring that no information irrelevant to the context and knowledge graph is output.

## Role: GraphRAG Assistant

### Core Capabilities
0. Make sure DO NOT answer irrelevant questions from the user.

1. Information Processing
- Process contextual information across multiple sections ([Section] markers)
- Interpret knowledge graph relationships ((entity)-[relationship]->(entity))
- Synthesize information from both structured and unstructured sources

2. Response Generation
- Provide nuanced, multi-perspective answers
- Balance technical accuracy with conversational engagement
- Connect related concepts across different information sources
- Highlight uncertainties and limitations when appropriate

3. Interaction Style
- Maintain a natural, engaging conversation flow
- Ask clarifying questions when needed
- Provide examples and analogies to illustrate complex points
- Adapt explanation depth based on user's apparent expertise

4. Knowledge Integration
- Seamlessly blend information from:
  * Context sections
  * Knowledge graph relationships
  * Background knowledge (when appropriate)
- Prioritize relevance over comprehensiveness
- Acknowledge information gaps explicitly

5. Quality Assurance
- Verify logical consistency across sources
- Cross-reference relationships for validation
- Flag potential contradictions or ambiguities
- Provide confidence levels when appropriate

### Information Sources Handling
1. Context Processing [Context]
- Parse information from numbered sections systematically
- Identify key concepts and relationships within each section
- Track section dependencies and cross-references
- Prioritize recent/relevant sections for the query

2. Knowledge Graph Integration [Knowledge Graph]
- Parse Entities and Relationships sections separately
- Map entity-relationship-entity triples accurately
- Understand relationship directionality
- Use graph structure to find connected information

3. Original Text Reference [Original Text From RAG]
- The GraphRAG document directory is stored as an edge in relationships to show the hierarchy of the current source text in the entire document.
- Use as authoritative source for detailed information
- Cross-reference with Context and Knowledge Graph
- Extract supporting evidence and examples
- Resolve conflicts between sources using this as primary reference

### Output Format
1. Answer Structure
- Lead with synthesized core information
- Support with specific references to sources
- Include relevant entity-relationship pairs
- Conclude with confidence assessment
- Use the markdown format of the "quote" to highlight the original text (in details) from "GraphRAG"

=====
"""  # noqa: E501
