"""Define the CommunitySummaryKnowledgeGraph."""

import logging
import os
import uuid
from typing import List, Optional, Tuple

from dbgpt.core import Chunk, Embeddings, LLMClient
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.graph_store.base import GraphStoreConfig
from dbgpt.storage.knowledge_graph.base import ParagraphChunk
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _
from dbgpt_ext.rag.retriever.graph_retriever.graph_retriever import GraphRetriever
from dbgpt_ext.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt_ext.rag.transformer.graph_embedder import GraphEmbedder
from dbgpt_ext.rag.transformer.graph_extractor import GraphExtractor
from dbgpt_ext.rag.transformer.text_embedder import TextEmbedder
from dbgpt_ext.storage.graph_store.tugraph_store import TuGraphStoreConfig
from dbgpt_ext.storage.knowledge_graph.community.community_store import CommunityStore
from dbgpt_ext.storage.knowledge_graph.knowledge_graph import (
    GRAPH_PARAMETERS,
    BuiltinKnowledgeGraph,
)

logger = logging.getLogger(__name__)


@register_resource(
    _("Community Summary KG Config"),
    "community_summary_kg_config",
    category=ResourceCategory.KNOWLEDGE_GRAPH,
    description=_("community Summary kg Config."),
    parameters=[
        *GRAPH_PARAMETERS,
        Parameter.build_from(
            _("Knowledge Graph Type"),
            "graph_store_type",
            str,
            description=_("graph store type."),
            optional=True,
            default="TuGraph",
        ),
        Parameter.build_from(
            _("LLM Client"),
            "llm_client",
            LLMClient,
            description=_("llm client for extract graph triplets."),
        ),
        Parameter.build_from(
            _("LLM Model Name"),
            "model_name",
            str,
            description=_("llm model name."),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("Vector Store Type"),
            "vector_store_type",
            str,
            description=_("vector store type."),
            optional=True,
            default="Chroma",
        ),
        Parameter.build_from(
            _("Topk of Knowledge Graph Extract"),
            "extract_topk",
            int,
            description=_("Topk of knowledge graph extract"),
            optional=True,
            default=5,
        ),
        Parameter.build_from(
            _("Recall Score of Knowledge Graph Extract"),
            "extract_score_threshold",
            float,
            description=_("Recall score of knowledge graph extract"),
            optional=True,
            default=0.3,
        ),
        Parameter.build_from(
            _("Recall Score of Community Search in Knowledge Graph"),
            "community_topk",
            int,
            description=_("Recall score of community search in knowledge graph"),
            optional=True,
            default=50,
        ),
        Parameter.build_from(
            _("Recall Score of Community Search in Knowledge Graph"),
            "community_score_threshold",
            float,
            description=_("Recall score of community search in knowledge graph"),
            optional=True,
            default=0.3,
        ),
        Parameter.build_from(
            _("Enable the graph search for documents and chunks"),
            "triplet_graph_enabled",
            bool,
            description=_("Enable the graph search for triplets"),
            optional=True,
            default=True,
        ),
        Parameter.build_from(
            _("Enable the graph search for documents and chunks"),
            "document_graph_enabled",
            bool,
            description=_("Enable the graph search for documents and chunks"),
            optional=True,
            default=True,
        ),
        Parameter.build_from(
            _("Top size of knowledge graph chunk search"),
            "knowledge_graph_chunk_search_top_size",
            int,
            description=_("Top size of knowledge graph chunk search"),
            optional=True,
            default=5,
        ),
        Parameter.build_from(
            _("Batch size of triplets extraction from the text"),
            "knowledge_graph_extraction_batch_size",
            int,
            description=_("Batch size of triplets extraction from the text"),
            optional=True,
            default=20,
        ),
        Parameter.build_from(
            _("Batch size of parallel community building process"),
            "community_summary_batch_size",
            int,
            description=_("TBatch size of parallel community building process"),
            optional=True,
            default=20,
        ),
    ],
)
@register_resource(
    _("Community Summary Knowledge Graph"),
    "community_summary_knowledge_graph",
    category=ResourceCategory.KNOWLEDGE_GRAPH,
    description=_("Community Summary Knowledge Graph."),
    parameters=[
        Parameter.build_from(
            _("Graph Store Config"),
            "config",
            GraphStoreConfig,
            description=_("graph store config."),
        ),
        Parameter.build_from(
            _("Graph Store Name"),
            "name",
            str,
            optional=True,
            default="dbgpt",
            description=_("Graph Store Name"),
        ),
        Parameter.build_from(
            _("LLM Client"),
            "llm_client",
            LLMClient,
            description=_("llm client for extract graph triplets."),
        ),
        Parameter.build_from(
            _("LLM Model Name"),
            "llm_model",
            str,
            description=_("kg extract llm model name."),
            optional=True,
            default=None,
        ),
    ],
)
class CommunitySummaryKnowledgeGraph(BuiltinKnowledgeGraph):
    """Community summary knowledge graph class."""

    def __init__(
        self,
        config: GraphStoreConfig,
        name: Optional[str] = "dbgpt",
        llm_client: Optional[LLMClient] = None,
        llm_model: Optional[str] = None,
        kg_extract_top_k: Optional[int] = 5,
        kg_extract_score_threshold: Optional[float] = 0.3,
        kg_community_top_k: Optional[int] = 50,
        kg_community_score_threshold: Optional[float] = 0.3,
        kg_triplet_graph_enabled: Optional[bool] = True,
        kg_document_graph_enabled: Optional[bool] = True,
        kg_chunk_search_top_k: Optional[int] = 5,
        kg_extraction_batch_size: Optional[int] = 3,
        kg_community_summary_batch_size: Optional[int] = 20,
        kg_embedding_batch_size: Optional[int] = 20,
        kg_similarity_top_k: Optional[int] = 5,
        kg_similarity_score_threshold: Optional[float] = 0.7,
        kg_enable_text_search: Optional[float] = False,
        kg_text2gql_model_enabled: Optional[bool] = False,
        kg_text2gql_model_name: Optional[str] = None,
        embedding_fn: Optional[Embeddings] = None,
        vector_store_config: Optional["VectorStoreConfig"] = None,
        kg_max_chunks_once_load: Optional[int] = 10,
        kg_max_threads: Optional[int] = 1,
    ):
        """Initialize community summary knowledge graph class."""
        super().__init__(
            config=config, name=name, llm_client=llm_client, llm_model=llm_model
        )
        self._config = config

        self._vector_store_type = config.get_type_value() or os.getenv(
            "VECTOR_STORE_TYPE"
        )
        self._extract_topk = int(
            kg_extract_top_k or os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE")
        )
        self._extract_score_threshold = float(
            kg_extract_score_threshold
            or os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE")
        )
        self._community_topk = int(
            kg_community_top_k or os.getenv("KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_TOP_SIZE")
        )
        self._community_score_threshold = float(
            kg_community_score_threshold
            or os.getenv("KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_RECALL_SCORE")
        )
        self._document_graph_enabled = kg_document_graph_enabled or (
            os.getenv("DOCUMENT_GRAPH_ENABLED", "").lower() == "true"
        )
        self._triplet_graph_enabled = kg_triplet_graph_enabled or (
            os.getenv("TRIPLET_GRAPH_ENABLED", "").lower() == "true"
        )
        self._triplet_extraction_batch_size = int(
            kg_extraction_batch_size
            or os.getenv("KNOWLEDGE_GRAPH_EXTRACTION_BATCH_SIZE")
        )
        self._triplet_embedding_batch_size = int(
            kg_embedding_batch_size or os.getenv("KNOWLEDGE_GRAPH_EMBEDDING_BATCH_SIZE")
        )
        self._community_summary_batch_size = int(
            kg_community_summary_batch_size or os.getenv("COMMUNITY_SUMMARY_BATCH_SIZE")
        )
        self._embedding_fn = embedding_fn
        self._vector_store_config = vector_store_config

        self._graph_extractor = GraphExtractor(
            self._llm_client,
            self._model_name,
            vector_store_config.create_store(
                name=name + "_CHUNK_HISTORY", embedding_fn=embedding_fn
            ),
            index_name=name,
            max_chunks_once_load=kg_max_chunks_once_load,
            max_threads=kg_max_threads,
            top_k=kg_extract_top_k,
            score_threshold=kg_extract_score_threshold,
        )

        self._graph_embedder = GraphEmbedder(embedding_fn)
        self._text_embedder = TextEmbedder(embedding_fn)

        # def community_store_configure(name: str, cfg: VectorStoreConfig):
        #     cfg.name = name
        #     cfg.embedding_fn = self._embedding_fn
        #     cfg.max_chunks_once_load = max_chunks_once_load
        #     cfg.max_threads = max_threads
        #     cfg.user = config.user
        #     cfg.password = config.password
        #     cfg.topk = self._community_topk
        #     cfg.score_threshold = self._community_score_threshold

        self._community_store = CommunityStore(
            self._graph_store_adapter,
            CommunitySummarizer(self._llm_client, self._model_name),
            vector_store_config.create_store(
                name=name + "_COMMUNITY_SUMMARY", embedding_fn=embedding_fn
            ),
            index_name=name,
            max_chunks_once_load=kg_max_chunks_once_load,
            max_threads=kg_max_threads,
            top_k=kg_community_top_k,
            score_threshold=kg_extract_score_threshold,
        )

        self._graph_retriever = GraphRetriever(
            self._graph_store_adapter,
            llm_client=llm_client,
            llm_model=llm_model,
            triplet_graph_enabled=kg_triplet_graph_enabled,
            document_graph_enabled=kg_document_graph_enabled,
            extract_top_k=kg_extract_top_k,
            kg_chunk_search_top_k=kg_chunk_search_top_k,
            similarity_top_k=kg_similarity_top_k,
            similarity_score_threshold=kg_similarity_score_threshold,
            embedding_fn=embedding_fn,
            embedding_batch_size=kg_embedding_batch_size,
            text2gql_model_enabled=kg_text2gql_model_enabled,
            text2gql_model_name=kg_text2gql_model_name,
        )

    def get_config(self) -> TuGraphStoreConfig:
        """Get the knowledge graph config."""
        return self._config

    @property
    def embeddings(self) -> Embeddings:
        """Get the knowledge graph config."""
        return self._embedding_fn

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist graph from the document file."""
        if not self.vector_name_exists():
            self._graph_store_adapter.create_graph(self._graph_name)
        await self._aload_document_graph(chunks)
        await self._aload_triplet_graph(chunks)
        await self._community_store.build_communities(
            batch_size=self._community_summary_batch_size
        )

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

        if self._graph_store.enable_similarity_search:
            # Add embeddings from chunk content
            texts: List[str] = [chunk.content for chunk in paragraph_chunks]

            embeddings = await self._text_embedder.batch_embed(
                inputs=texts,
                batch_size=self._triplet_embedding_batch_size,
            )

            for idx, chunk in enumerate(paragraph_chunks):
                chunk.embedding = embeddings[idx]

        # upsert the document and chunks vertices
        self._graph_store_adapter.upsert_documents(iter([documment_chunk]))
        self._graph_store_adapter.upsert_chunks(iter(paragraph_chunks))

        # upsert the document structure
        for chunk_index, chunk in enumerate(paragraph_chunks):
            # document -> include -> chunk
            if chunk.parent_is_document:
                self._graph_store_adapter.upsert_doc_include_chunk(chunk=chunk)
            else:  # chunk -> include -> chunk
                self._graph_store_adapter.upsert_chunk_include_chunk(chunk=chunk)

            # chunk -> next -> chunk
            if chunk_index >= 1:
                self._graph_store_adapter.upsert_chunk_next_chunk(
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
        if not graphs_list:
            raise ValueError("No graphs extracted from the chunks")

        # If enable the similarity search, add the embedding to the graphs
        if self._graph_store.enable_similarity_search:
            for idx, graphs in enumerate(graphs_list):
                embeded_graphs = await self._graph_embedder.batch_embed(
                    inputs=graphs,
                    batch_size=self._triplet_embedding_batch_size,
                )
                graphs_list[idx] = embeded_graphs

        # Upsert the graphs into the graph store
        for idx, graphs in enumerate(graphs_list):
            for graph in graphs:
                if document_graph_enabled:
                    # Append the chunk id to the edge
                    for edge in graph.edges():
                        edge.set_prop("_chunk_id", chunks[idx].chunk_id)
                        graph.append_edge(edge=edge)

                # Upsert the graph
                self._graph_store_adapter.upsert_graph(graph)

                # chunk -> include -> entity
                if document_graph_enabled:
                    for vertex in graph.vertices():
                        self._graph_store_adapter.upsert_chunk_include_entity(
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

        # chunk.metadata = {"Header0": "title",
        # "Header1": "title", ..., "source": "source_path"}  # noqa: E501
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

        (
            subgraph,
            (
                subgraph_for_doc,
                text2gql_query,
            ),
        ) = await self._graph_retriever.retrieve(text)

        knowledge_graph_str = subgraph.format() if subgraph else ""
        knowledge_graph_for_doc_str = (
            subgraph_for_doc.format() if subgraph_for_doc else ""
        )
        if not (summaries or knowledge_graph_str or knowledge_graph_for_doc_str):
            return []

        # merge search results into context
        content = HYBRID_SEARCH_PT.format(
            context=context,
            query=text2gql_query,
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
        logger.info("Truncate graph embedder")
        self._graph_embedder.truncate()
        logger.info("Truncate text embedder")
        self._text_embedder.truncate()
        return [self._graph_name]

    def delete_vector_name(self, index_name: str):
        """Delete knowledge graph."""
        logger.info("Drop community store")
        self._community_store.drop()

        logger.info("Drop keyword extractor")
        self._keyword_extractor.drop()

        logger.info("Drop triplet extractor")
        self._graph_extractor.drop()

        logger.info("Drop graph embedder")
        self._graph_embedder.drop()

        logger.info("Drop text embedder")
        self._text_embedder.drop()


HYBRID_SEARCH_PT = """
=====
The following information from [Context], [Graph Query Statement], [Knowledge Graph], and [Original Text From RAG] can help you answer user questions better.

[Context]:
{context}

[Graph Query Statement]:
{query}

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

4. Original Graph Query [Graph Query Statement]
- The graph query statement used if text2gql translation is successful
- Graph query will be empty if the translation failed
- Use the markdown code block format to highlight the graph query statement if the statement is not empty

### Output Format
1. Answer Structure
- Lead with a markdown code block to highlight the original cypher query statement from [Graph Query Statement] if it's not empty
- Demonstate synthesized core information
- Support with specific references to sources
- Include relevant entity-relationship pairs
- Conclude with confidence assessment
- Use the markdown format of the "quote" to highlight the original text (in details) from "GraphRAG"

=====
"""  # noqa: E501
