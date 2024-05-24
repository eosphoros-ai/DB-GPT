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
        self._config = config
        super().__init__()
        self._llm_client = config.llm_client
        if not self._llm_client:
            raise ValueError("No llm client provided.")

        self._model_name = config.model_name
        self._triplet_extractor = TripletExtractor(self._llm_client, self._model_name)
        self._keyword_extractor = KeywordExtractor(self._llm_client, self._model_name)
        self._graph_store_type = (
            os.getenv("GRAPH_STORE_TYPE", "TuGraph") or config.graph_store_type
        )

        def configure(cfg: GraphStoreConfig):
            cfg.name = self._config.name
            cfg.embedding_fn = self._config.embedding_fn

        self._graph_store: GraphStoreBase = GraphStoreFactory.create(
            self._graph_store_type, configure
        )

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist triplets to graph store."""

        async def process_chunk(chunk):
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                self._graph_store.insert_triplet(*triplet)
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
                self._graph_store.insert_triplet(*triplet)
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

    def query_graph(self, limit: Optional[int] = None) -> Graph:
        """Query graph."""
        return self._graph_store.get_full_graph(limit)

    def delete_vector_name(self, index_name: str):
        """Delete vector name."""
        logger.info(f"Remove graph index {index_name}")
        self._graph_store.drop()
