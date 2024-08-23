"""Define the CommunitySummaryKnowledgeGraph class inheriting from BuiltinKnowledgeGraph."""

import logging
import os
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.rag.transformer.graph_extractor import GraphExtractor
from dbgpt.storage.graph_store.community_store import CommunityStore
from dbgpt.storage.graph_store.graph import Edge, MemoryGraph, Vertex
from dbgpt.storage.knowledge_graph.community.factory import \
    CommunityStoreAdapterFactory
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
        default="Chroma", description="The type of vector store."
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description=(
            "The password of vector store, if not set, will use the default password."
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
        default=0.3,
        description="Recall score of community search in knowledge graph",
    )


class CommunitySummaryKnowledgeGraph(BuiltinKnowledgeGraph):
    """Community summary knowledge graph class."""

    def __init__(self, config: CommunitySummaryKnowledgeGraphConfig):
        super().__init__(config)
        self._config = config

        self._vector_store_type = os.getenv(
            "VECTOR_STORE_TYPE", config.vector_store_type
        )
        self._extract_topk = os.getenv(
            "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE", config.extract_topk
        )
        self._extract_score_threshold = os.getenv(
            "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE",
            config.extract_score_threshold,
        )
        self._community_topk = os.getenv(
            "KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_TOP_SIZE", config.community_topk
        )
        self._community_score_threshold = os.getenv(
            "KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_RECALL_SCORE",
            config.community_score_threshold
        )

        def configure(name: str, cfg: VectorStoreConfig):
            cfg.name = name
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password

        self._triplet_extractor = GraphExtractor(
            self._llm_client,
            self._model_name,
            VectorStoreFactory.create(
                self._vector_store_type,
                config.name + "_CHUNK_HISTORY",
                configure
            )
        )
        self._community_store = CommunityStore(
            CommunityStoreAdapterFactory.create(self._graph_store),
            CommunitySummarizer(
                self._llm_client, self._model_name
            ),
            VectorStoreFactory.create(
                self._vector_store_type,
                config.name + "_COMMUNITY_SUMMARY",
                configure
            )
        )

    def get_config(self) -> BuiltinKnowledgeGraphConfig:
        """Get the knowledge graph config."""
        return self._config

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        # Load documents as chunks
        memory_graph = MemoryGraph()
        # todo add doc node
        for chunk in chunks:
            # Extract triplets from each chunk
            triplets = await self._triplet_extractor.extract(chunk.content)
            # todo add chunk node
            # todo add relation doc-chunk
            for triplet in triplets:
                # Insert each triplet into the graph store
                # if triplet.get("type") == "triplet":
                #     data = triplet.get("data")
                #     self._graph_store.insert_triplet(*data)
                if triplet.get("type") == "node":
                    data = triplet.get("data")
                    id = data.get('node')
                    desc = data.get("description")
                    vertex = Vertex(id,description=desc)
                    memory_graph.upsert_vertex(vertex)
                    # todo add relation chunk-vertex
                elif triplet.get("type") == "edge":
                    data = triplet.get("data")
                    edge_data = data.get("triplet")
                    desc = data.get("description")
                    sid = edge_data[0]
                    tid = edge_data[2]
                    label = edge_data[1]
                    edge = Edge(sid,tid,label=label,description = desc)
                    memory_graph.append_edge(edge)
            logger.info(
                f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
        # Build communities after loading all triplets
        self._graph_store.insert_graph(memory_graph)
        await self._community_store.build_communities()
        return [chunk.chunk_id for chunk in chunks]

    async def asimilar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        # Perform both global and local searches
        global_results = await self._global_search(text, topk, score_threshold,
                                                   filters)
        local_results = await self._local_search(text, topk, score_threshold,
                                                 filters)

        # Combine results, keeping original order and scores
        combined_results = global_results + local_results
       
        # Add a source field to distinguish between global and local results
        for chunk in combined_results[: len(global_results)]:
            chunk.metadata["source"] = "global"
        for chunk in combined_results[len(local_results):]:
            chunk.metadata["source"] = "local"

        # Return all results
        return combined_results

    async def _global_search(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        # Use the community metastore to perform vector search
        relevant_communities = await self._community_store.search_communities(text)

        return [
            Chunk(content=c.summary, metadata={"cluster_id": c.id})
            for c in relevant_communities
        ]

        # # Generate answers from the top-k community summaries
        # chunks = []
        # for community in relevant_communities[:topk]:
        #     answer = await self._generate_answer_from_summary(
        #         community.summary, text
        #     )
        #     chunks.append(
        #         Chunk(content=answer, metadata={"cluster_id": community.id})
        #     )
        #
        # return chunks

    async def _local_search(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        return await super().asimilar_search_with_scores(
            text, topk, score_threshold, filters
        )

    async def _generate_answer_from_summary(self, community_summary, query):
        """Generate an answer from a community summary based on a given query using LLM."""
        prompt_template = """Given the community summary: {summary}, answer the following query.

        Query: {query}

        Answer:"""

        return await self._triplet_extractor.extract(
            prompt_template.format(summary=community_summary, query=query)
        )

    def delete_vector_name(self, index_name: str):
        super().delete_vector_name(index_name)
        self._community_store.drop()
