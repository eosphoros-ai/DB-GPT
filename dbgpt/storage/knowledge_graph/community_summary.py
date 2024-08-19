"""Define the CommunitySummaryKnowledgeGraph class inheriting from BuiltinKnowledgeGraph."""

import logging
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.rag.transformer.graph_extractor import GraphExtractor
from dbgpt.storage.graph_store.community_store import CommunityStore
from dbgpt.storage.knowledge_graph.community.community_metastore import (
    BuiltinCommunityMetastore,
)
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)
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

        self._triplet_extractor = GraphExtractor(
            self._llm_client, self._model_name, config
        )
        self._community_metastore = BuiltinCommunityMetastore(config)
        self._community_store = CommunityStore(
            self._graph_store, self._community_metastore
        )

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        # Load documents as chunks
        for chunk in chunks:
            # Extract triplets from each chunk
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                # Insert each triplet into the graph store
                self._graph_store.insert_triplet(*triplet)
            logger.info(f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
        # Build communities after loading all triplets
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
        global_results = await self._global_search(text, topk, score_threshold, filters)
        local_results = await self._local_search(text, topk, score_threshold, filters)

        # Combine results, keeping original order and scores
        combined_results = global_results + local_results

        # Add a source field to distinguish between global and local results
        for chunk in combined_results[: len(global_results)]:
            chunk.metadata["source"] = "global"
        for chunk in combined_results[len(global_results) :]:
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
        relevant_communities = await self._community_metastore.search(text)

        # Generate answers from the top-k community summaries
        chunks = []
        for community in relevant_communities[:topk]:
            answer = await self._generate_answer_from_summary(community.summary, text)
            chunks.append(Chunk(content=answer, metadata={"cluster_id": community.id}))

        return chunks

    async def _local_search(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search neighbours on knowledge graph."""
        if not filters:
            logger.info("Filters on knowledge graph not supported yet")

        # extract keywords and explore graph store
        keywords = await self._keyword_extractor.extract(text)
        subgraph = self._graph_store.explore(keywords, limit=topk)
        logger.info(f"Search subgraph from {len(keywords)} keywords")

        content = (
            "The following vertices and edges data after [Subgraph Data] "
            "are retrieved from the knowledge graph based on the keywords:\n"
            f"Keywords:\n{','.join(keywords)}\n"
            "---------------------\n"
            "You can refer to the sample vertices and edges to understand "
            "the real knowledge graph data provided by [Subgraph Data].\n"
            "Sample vertices:\n"
            "(alice)\n"
            "(bob:{age:28})\n"
            '(carry:{age:18;role:"teacher"})\n\n'
            "Sample edges:\n"
            "(alice)-[reward]->(alice)\n"
            '(alice)-[notify:{method:"email"}]->'
            '(carry:{age:18;role:"teacher"})\n'
            '(bob:{age:28})-[teach:{course:"math";hour:180}]->(alice)\n'
            "---------------------\n"
            f"Subgraph Data:\n{subgraph.format()}\n"
        )
        return [Chunk(content=content, metadata=subgraph.schema())]

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
        self._community_metastore.drop()
