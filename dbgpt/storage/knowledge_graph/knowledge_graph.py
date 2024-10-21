"""Knowledge graph class."""

import asyncio
import logging
import os
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.rag.transformer.triplet_extractor import TripletExtractor
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.factory import GraphStoreFactory
from dbgpt.storage.graph_store.graph import Graph
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase, KnowledgeGraphConfig
from dbgpt.storage.knowledge_graph.community.base import GraphStoreAdapter
from dbgpt.storage.knowledge_graph.community.factory import GraphStoreAdapterFactory
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class BuiltinKnowledgeGraphConfig(KnowledgeGraphConfig):
    """Builtin knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_client: LLMClient = Field(default=None, description="The default llm client.")

    model_name: str = Field(default=None, description="The name of llm model.")

    graph_store_type: str = Field(
        default="TuGraph", description="The type of graph store."
    )


class BuiltinKnowledgeGraph(KnowledgeGraphBase):
    """Builtin knowledge graph class."""

    def __init__(self, config: BuiltinKnowledgeGraphConfig):
        """Create builtin knowledge graph instance."""
        super().__init__()
        self._config = config

        self._llm_client = config.llm_client
        if not self._llm_client:
            raise ValueError("No llm client provided.")

        self._model_name = config.model_name
        self._triplet_extractor = TripletExtractor(self._llm_client, self._model_name)
        self._keyword_extractor = KeywordExtractor(self._llm_client, self._model_name)
        self._graph_store: GraphStoreBase = self.__init_graph_store(config)
        self._graph_store_apdater: GraphStoreAdapter = self.__init_graph_store_adapter()

    def __init_graph_store(self, config: BuiltinKnowledgeGraphConfig) -> GraphStoreBase:
        def configure(cfg: GraphStoreConfig):
            cfg.name = config.name
            cfg.embedding_fn = config.embedding_fn

        graph_store_type = os.getenv("GRAPH_STORE_TYPE") or config.graph_store_type
        return GraphStoreFactory.create(graph_store_type, configure)

    def __init_graph_store_adapter(self):
        return GraphStoreAdapterFactory.create(self._graph_store)

    def get_config(self) -> BuiltinKnowledgeGraphConfig:
        """Get the knowledge graph config."""
        return self._config

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist triplets to graph store."""

        async def process_chunk(chunk: Chunk):
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                self._graph_store_apdater.insert_triplet(*triplet)
            logger.info(f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
            return chunk.chunk_id

        # wait async tasks completed
        tasks = [process_chunk(chunk) for chunk in chunks]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()
        return result

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:  # type: ignore
        """Extract and persist triplets to graph store.

        Args:
            chunks: List[Chunk]: document chunks.
        Return:
            List[str]: chunk ids.
        """
        for chunk in chunks:
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                self._graph_store_apdater.insert_triplet(*triplet)
            logger.info(f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
        return [chunk.chunk_id for chunk in chunks]

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search neighbours on knowledge graph."""
        raise Exception("Sync similar_search_with_scores not supported")

    async def asimilar_search_with_scores(
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
        subgraph = self._graph_store_apdater.explore(keywords, limit=topk).format()

        logger.info(f"Search subgraph from {len(keywords)} keywords")

        if not subgraph:
            return []

        content = (
            "The following entities and relationships provided after "
            "[Subgraph] are retrieved from the knowledge graph "
            "based on the keywords:\n"
            f"\"{','.join(keywords)}\".\n"
            "---------------------\n"
            "The following examples after [Entities] and [Relationships] that "
            "can help you understand the data format of the knowledge graph, "
            "but do not use them in the answer.\n"
            "[Entities]:\n"
            "(alice)\n"
            "(bob:{age:28})\n"
            '(carry:{age:18;role:"teacher"})\n\n'
            "[Relationships]:\n"
            "(alice)-[reward]->(alice)\n"
            '(alice)-[notify:{method:"email"}]->'
            '(carry:{age:18;role:"teacher"})\n'
            '(bob:{age:28})-[teach:{course:"math";hour:180}]->(alice)\n'
            "---------------------\n"
            f"[Subgraph]:\n{subgraph}\n"
        )
        return [Chunk(content=content)]

    def query_graph(self, limit: Optional[int] = None) -> Graph:
        """Query graph."""
        return self._graph_store_apdater.get_full_graph(limit)

    def truncate(self) -> List[str]:
        """Truncate knowledge graph."""
        logger.info(f"Truncate graph {self._config.name}")
        self._graph_store_apdater.truncate()

        logger.info("Truncate keyword extractor")
        self._keyword_extractor.truncate()

        logger.info("Truncate triplet extractor")
        self._triplet_extractor.truncate()

        return [self._config.name]

    def delete_vector_name(self, index_name: str):
        """Delete vector name."""
        logger.info(f"Drop graph {index_name}")
        self._graph_store_apdater.drop()

        logger.info("Drop keyword extractor")
        self._keyword_extractor.drop()

        logger.info("Drop triplet extractor")
        self._triplet_extractor.drop()

    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete by ids."""
        self._graph_store_apdater.delete_document(chunk_id=ids)
        return []
