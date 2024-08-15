"""Define the CommunitySummaryKnowledgeGraph class inheriting from BuiltinKnowledgeGraph."""

import logging
from typing import List, Optional

from openai import OpenAI

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.rag.transformer.summary_triplet_extractor import SummaryTripletExtractor
from dbgpt.storage.graph_store.community_store import CommunityStore
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)
client = OpenAI(api_key="")


class CommunitySummaryKnowledgeGraphConfig(BuiltinKnowledgeGraphConfig):
    """Community summary knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CommunitySummaryKnowledgeGraph(BuiltinKnowledgeGraph):
    """Community summary knowledge graph class."""

    def __init__(self, config: CommunitySummaryKnowledgeGraphConfig):
        super().__init__(config)

        self._triplet_extractor = SummaryTripletExtractor(
            self._llm_client, self._model_name
        )

        # Initialize CommunityStore with a graph storage instance
        self.community_store = CommunityStore(self._graph_store)

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
        await self.community_store.build_communities()
        return [chunk.chunk_id for chunk in chunks]

    async def asimilar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:

        # Determine if search is global or local
        is_global_search = await self._get_intent_from_query(text)
        return await (self._global_search if is_global_search else self._local_search)(
            text, topk, score_threshold, filters
        )

    async def _global_search(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        community_summaries = await self.community_store.summarize_communities()
        chunks = [
            Chunk(
                content=await self._generate_answer_from_summary(summary, text),
                metadata={"cluster_id": cluster_id},
            )
            for cluster_id, summary in community_summaries.items()
        ]
        return chunks[:topk]

        #     final_answer = self._aggregate_answers(community_summaries)
        # return final_answer

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
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"Given the community summary: {community_summary}, answer the following query.",
                },
                {"role": "user", "content": query},
            ],
        )
        return response.choices[0].message.content.strip()

    async def _aggregate_answers(self, community_answers):
        """Aggregate individual community answers into a final, coherent response."""
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Combine the following intermediate answers into a final, concise response.",
                },
                {
                    "role": "user",
                    "content": f"Intermediate answers: {' '.join(community_answers)}",
                },
            ],
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    async def _get_intent_from_query(query: str) -> bool:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Determine if the given query is abstract (global) or concrete (local). Respond with 'global' or 'local'.",
                },
                {"role": "user", "content": query},
            ],
        )
        return response.choices[0].message.content.strip().lower() == "global"
