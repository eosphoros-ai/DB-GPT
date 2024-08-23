"""Define the CommunitySummaryKnowledgeGraph class inheriting from BuiltinKnowledgeGraph."""

import logging
import os
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.rag.transformer.graph_extractor import GraphExtractor
from dbgpt.storage.graph_store.community_store import CommunityStore
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
        # todo add doc node
        for chunk in chunks:
            # Extract triplets from each chunk
            graph = await self._triplet_extractor.extract(chunk.content)
            # todo add chunk node
            # todo add relation doc-chunk
            self._graph_store.insert_graph(graph)
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
        # global search: retrieve relevant community summaries
        communities = await self._community_store.search_communities(text)
        summaries = "\n".join([c.summary for c in communities])

        # local search: extract keywords and explore subgraph
        keywords = await self._keyword_extractor.extract(text)
        subgraph = self._graph_store.explore(keywords, limit=topk).format()
        logger.info(f"Search subgraph from {len(keywords)} keywords")

        if not summaries and not subgraph:
            return []

        content = (
            "The following entities and relations provided after [SUBGRAPH] "
            "are retrieved from the knowledge graph based on the keywords:\n"
            f"\"{','.join(keywords)}\".\n"
            "The text provided after [SUMMARY] is a summary supplement "
            "to the entities and relations."
            "---------------------\n"
            "The following examples after [ENTITIES] and [RELATIONS] that "
            "can help you understand the data format of the knowledge graph, "
            "but do not use them in the answer.\n"
            "[ENTITIES]:\n"
            "(alice)\n"
            "(bob:{age:28})\n"
            '(carry:{age:18;role:"teacher"})\n\n'
            "[RELATIONS]:\n"
            "(alice)-[reward]->(alice)\n"
            '(alice)-[notify:{method:"email"}]->'
            '(carry:{age:18;role:"teacher"})\n'
            '(bob:{age:28})-[teach:{course:"math";hour:180}]->(alice)\n'
            "---------------------\n"
            f"[SUBGRAPH]:\n{subgraph}\n"
            f"[SUMMARY]:\n{summaries}\n"
        )

        return [Chunk(content=content)]

    def delete_vector_name(self, index_name: str):
        logger.info(f"Remove community store")
        self._community_store.drop()

        logger.info(f"Clean keyword extractor")
        self._keyword_extractor.clean()

        logger.info(f"Clean triplet extractor")
        self._triplet_extractor.clean()


