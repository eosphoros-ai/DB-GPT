"""Knowledge graph class."""
import asyncio
import logging
import os
from typing import Optional, List

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.rag.transformer.triplet_extractor import TripletExtractor
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.factory import GraphStoreFactory
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase, \
    KnowledgeGraphConfig
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class BuiltinKnowledgeGraphConfig(KnowledgeGraphConfig):
    """Builtin knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_client: LLMClient = Field(
        default=None,
        description="The default llm client."
    )

    model_name: str = Field(
        default=None,
        description="The name of llm model."
    )

    graph_store_type: str = Field(
        default=None,
        description="The type of graph store."
    )


class BuiltinKnowledgeGraph(KnowledgeGraphBase):
    """Builtin knowledge graph class."""

    def __init__(
        self,
        config: BuiltinKnowledgeGraphConfig
    ):
        """Create builtin knowledge graph instance."""
        self._config = config

        self._llm_client = config.llm_client
        if not self._llm_client:
            raise ValueError("No llm client provided.")

        self._model_name = config.model_name
        self._triplet_extractor = TripletExtractor(
            self._llm_client,
            self._model_name
        )
        self._keyword_extractor = KeywordExtractor(
            self._llm_client,
            self._model_name
        )
        self._graph_store_type = (
            config.graph_store_type
            or os.getenv("GRAPH_STORE_TYPE", "TuGraph")
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
            return chunk.chunk_id

        # wait async tasks completed
        tasks = [process_chunk(chunk) for chunk in chunks]
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(asyncio.gather(*tasks))

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search neighbours on knowledge graph."""
        if not filters:
            raise ValueError("Filters on knowledge graph not supported yet")

        # extract keywords and explore graph store
        async def process_query(query):
            keywords = await self._keyword_extractor.extract(query)
            subgraph = self._graph_store.explore(keywords, limit=topk)
            return [
                Chunk(content=subgraph.format(), metadata=subgraph.schema())]

        # wait async task completed
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(asyncio.gather(*[process_query(text)]))

    def delete_vector_name(self, index_name: str):
        self._graph_store.drop()
